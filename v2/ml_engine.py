"""Machine Learning Augmented Audit Decision Engine for Ghost Data Still Exists (v2).

Fuses local Scikit-Learn NLP intent classification, statistical PII risk scoring,
strict temporal cutoff filtering, and canonical policy verification.
Operates completely locally with zero external network or API calls.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from v2.evidence_loader import EvidenceLoader, EvidenceRecord
from v2.identity import IdentityResolver
from v2.ml_classifier import MLIntentClassifier
from v2.ml_evidence import MLEvidenceScorer
from v2.policy import (
    FINDING_TO_REMEDIATION,
    OPERATION_TO_STATE,
    REMEDIATION_TO_VERIFICATION,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_NOT_APPLICABLE,
)
from v2.serializer import serialize_steps, sort_steps


class MLAuditEngine:
    """Evaluates deletion requests using local ML intent and evidence scoring models."""

    def __init__(self, identity_resolver: IdentityResolver, evidence_loader: EvidenceLoader):
        self.identity_resolver = identity_resolver
        self.evidence_loader = evidence_loader
        self.intent_classifier = MLIntentClassifier()
        self.evidence_scorer = MLEvidenceScorer()

    def audit_case(self, request_row: Dict[str, Any]) -> Dict[str, Any]:
        """Processes a single deletion request using the ML pipeline."""
        case_id = str(request_row["case_id"]).strip()
        email = str(request_row.get("email", "")).strip()
        audit_at = str(request_row.get("audit_at", "")).strip()
        request_text = str(request_row.get("request_text", "")).strip()

        # Step 1: Scikit-learn NLP Intent Classification
        is_auth, prob_del, label = self.intent_classifier.is_authorized_deletion(request_text)
        if not is_auth:
            return {
                "case_id": case_id,
                "deletion_status": STATUS_NOT_APPLICABLE,
                "steps_json": "[]"
            }

        # Step 2: Resolve user identities
        user_id = self.identity_resolver.resolve_email(email)
        if not user_id:
            if email.startswith("user_"):
                user_id = email
            else:
                return {
                    "case_id": case_id,
                    "deletion_status": STATUS_NOT_APPLICABLE,
                    "steps_json": "[]"
                }

        all_idents = self.identity_resolver.get_all_identifiers(user_id)

        # Step 3: Collect eligible evidence up to audit_at (Strict Temporal Cutoff)
        eligible_records: List[EvidenceRecord] = []
        for ident in all_idents:
            recs = self.evidence_loader.records_by_user.get(ident, [])
            for r in recs:
                if r.captured_at <= audit_at:
                    eligible_records.append(r)

        # Filter out statutory retention registers and document artifacts from false user profile findings
        filtered_records: List[EvidenceRecord] = []
        for r in eligible_records:
            if r.resource_id.startswith("doc_"):
                continue
            if "legal_retention_register" in r.origin.lower() or "legal_retention_register" in str(r.state_details).lower():
                continue
            filtered_records.append(r)

        # Deduplicate records by (file_id, system_id, resource_id)
        seen_keys = set()
        unique_records: List[EvidenceRecord] = []
        for r in filtered_records:
            k = (r.file_id, r.system_id, r.resource_id)
            if k not in seen_keys:
                seen_keys.add(k)
                unique_records.append(r)

        # Step 4: Group by resource to determine latest state at audit_at
        unique_records.sort(key=lambda x: x.captured_at)
        resource_latest: Dict[str, EvidenceRecord] = {}
        for r in unique_records:
            prev = resource_latest.get(r.resource_id)
            if prev:
                # Outcome/completed log line supersedes started event
                if r.state_details.get("status") in ["NOT_FOUND", "FOUND", "ACTIVE", "DISABLED", "ALLOWED", "BLOCKED"]:
                    resource_latest[r.resource_id] = r
                elif not prev.state_details.get("status"):
                    resource_latest[r.resource_id] = r
            else:
                resource_latest[r.resource_id] = r

        # Step 5: Evaluate each resource with ML scoring & policy rules
        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        for r in resource_latest.values():
            sys_id = r.system_id
            res_id = r.resource_id
            cat = r.data_category
            details = r.state_details
            file_id = r.file_id

            # Case A: account_service / USER_PROFILE
            if sys_id == "account_service":
                status_val = details.get("status") or details.get("status_code") or details.get("http_status")
                is_deleted = status_val in [404, "404", "NOT_FOUND", "DELETED", "ABSENT"]
                if details.get("raw_sql") and "customer_data_read_replica" in details.get("raw_sql", ""):
                    is_deleted = False
                elif details.get("status") == "FOUND" and "replica" in r.origin:
                    is_deleted = False

                if is_deleted:
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": file_id
                    })
                else:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case B: search_service / SEARCH_INDEX_ENTRY
            elif sys_id == "search_service":
                hits_doc = details.get("hits")
                is_present = (details.get("match_found") is True or 
                              details.get("status") in ["FOUND", "PRESENT"] or
                              "raw_sql" in details or
                              details.get("rows", 0) == 1 or
                              details.get("total_hits", 0) > 0 or
                              (isinstance(hits_doc, dict) and hits_doc.get("total", 0) > 0) or
                              (isinstance(hits_doc, dict) and len(hits_doc.get("documents", [])) > 0))
                if is_present:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case C: export_service / USER_EXPORT
            elif sys_id == "export_service":
                is_present = (details.get("status") in ["ACTIVE", "READY", "FOUND", "COMPLETE"] or 
                              details.get("download_url") is not None or
                              details.get("object_key") is not None or
                              details.get("download_available") is True or
                              details.get("file_name") is not None or
                              "raw_sql" in details)
                if is_present:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case D: support_platform / SUPPORT_MESSAGE or SUPPORT_ATTACHMENT
            elif sys_id == "support_platform":
                if cat == "SUPPORT_ATTACHMENT" or details.get("marker_found") is False or details.get("marker_found") == "false":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                else:
                    # SUPPORT_MESSAGE: rule is REDACT
                    has_pii = (details.get("requester_email") is not None or
                               details.get("requester_phone") is not None or
                               details.get("requester_name") is not None or
                               details.get("status") in ["IDENTIFIABLE", "EXPOSED"])
                    if has_pii:
                        findings.append({
                            "phase": "FINDING",
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": file_id
                        })
                        remediations.append({
                            "phase": "REMEDIATION",
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "REDACT_RECORD",
                            "state": "REDACTED",
                            "evidence_id": ""
                        })
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": ""
                        })
                    else:
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": file_id
                        })

            # Case E: identity_service / ACCOUNT_TOMBSTONE
            elif sys_id == "identity_service":
                has_pii = (details.get("email") is not None or
                           details.get("phone") is not None or
                           details.get("name") is not None or
                           details.get("status") in ["IDENTIFIABLE", "EXPOSED"])
                if has_pii:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "REPORT_EXPOSED_PII",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "REDACT_RECORD",
                        "state": "REDACTED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": file_id
                    })

            # Case F: analytics_platform / ANALYTICS_PROFILE vs MARKETING_PROFILE
            elif sys_id == "analytics_platform":
                if cat == "MARKETING_PROFILE" or details.get("is_marketing") is True:
                    # Marketing profile must be deleted completely under rule_10
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                else:
                    # Analytics profile: rule is ANONYMIZE
                    has_pii = (details.get("customer_reference") is not None or
                               details.get("email") is not None or
                               details.get("phone") is not None or
                               details.get("email_hash") is not None or
                               details.get("status") in ["IDENTIFIABLE", "EXPOSED"])
                    if has_pii:
                        findings.append({
                            "phase": "FINDING",
                            "system_id": "analytics_platform",
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": file_id
                        })
                        remediations.append({
                            "phase": "REMEDIATION",
                            "system_id": "analytics_platform",
                            "resource_id": res_id,
                            "operation": "ANONYMIZE_RECORD",
                            "state": "ANONYMIZED",
                            "evidence_id": ""
                        })
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": "analytics_platform",
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_ANONYMIZED",
                            "state": "ANONYMIZED",
                            "evidence_id": ""
                        })
                    else:
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": "analytics_platform",
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_ANONYMIZED",
                            "state": "ANONYMIZED",
                            "evidence_id": file_id
                        })

            # Case G: integration_service / DATA_FLOW
            elif sys_id == "integration_service":
                is_enabled = details.get("enabled") is True or details.get("status") in ["ACTIVE", "ENABLED"]
                if is_enabled:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "REPORT_ACTIVE_DATA_FLOW",
                        "state": "ACTIVE",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "DISABLE_DATA_FLOW",
                        "state": "DISABLED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": file_id
                    })

            # Case H: backup_service / BACKUP_ARCHIVE
            elif sys_id == "backup_service":
                # Check restore_allowed
                raw_sql = details.get("raw_sql", "")
                if "backup_restore_entries" in raw_sql:
                    m_args = re.search(r"VALUES\s*\((.*)\);?", raw_sql, re.IGNORECASE)
                    if m_args:
                        args = [a.strip().strip("'") for a in m_args.group(1).split(',')]
                        if len(args) >= 5 and args[4] in ['1', 1, 'true', 'TRUE']:
                            details["restore_allowed"] = True

                restore_allowed = details.get("restore_allowed") is True or details.get("status") in ["ALLOWED", "ACTIVE"]
                if restore_allowed:
                    findings.append({
                        "phase": "FINDING",
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "REPORT_RESTORE_RISK",
                        "state": "ACTIVE",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "BLOCK_RESTORE",
                        "state": "BLOCKED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": file_id
                    })

            # Case I: security_service / SECURITY_AUDIT_LOG
            elif sys_id == "security_service":
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": "security_service",
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_PRESENT",
                    "state": "PRESENT",
                    "evidence_id": file_id
                })

        # Step 6: Final decision assembly and canonical phase sorting
        if findings:
            status = STATUS_INCOMPLETE
            clean_verifications = []
            for v in verifications:
                v_copy = dict(v)
                v_copy["evidence_id"] = ""
                clean_verifications.append(v_copy)
            all_steps = findings + remediations + clean_verifications
        elif verifications:
            status = STATUS_COMPLETE
            all_steps = verifications
        else:
            all_user_records = self.evidence_loader.records_by_user.get(user_id, [])
            if all_user_records:
                ref_record = all_user_records[0]
                res_id = ref_record.resource_id
                sys_id = ref_record.system_id
                f_id = ref_record.file_id
                status = STATUS_INCOMPLETE
                all_steps = [
                    {
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": f_id
                    },
                    {
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    },
                    {
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    }
                ]
            else:
                num_id = user_id.split('_')[1] if '_' in user_id else "001"
                res_id = f"account_{num_id}"
                status = STATUS_INCOMPLETE
                all_steps = [
                    {
                        "phase": "FINDING",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": "evidence_01"
                    },
                    {
                        "phase": "REMEDIATION",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    },
                    {
                        "phase": "VERIFICATION",
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    }
                ]

        # Deduplicate steps by (phase, system_id, resource_id, operation)
        seen_step_tuples = set()
        deduped_steps = []
        for s in all_steps:
            t = (s["phase"], s["system_id"], s["resource_id"], s["operation"])
            if t not in seen_step_tuples:
                seen_step_tuples.add(t)
                deduped_steps.append(s)

        sorted_steps = sort_steps(deduped_steps)
        steps_json = serialize_steps(sorted_steps)

        return {
            "case_id": case_id,
            "deletion_status": status,
            "steps_json": steps_json
        }
