"""Audit decision engine for Ghost Data Still Exists.

Reconstructs the ground-truth state of each user's resources at audit_at,
evaluates deletion compliance against deletion_rules.csv, and produces
findings, remediation, and verification steps.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from code.classifier import RequestClassifier
from code.evidence_loader import EvidenceLoader, EvidenceRecord
from code.identity import IdentityResolver
from code.policy import (
    FINDING_TO_REMEDIATION,
    OPERATION_TO_STATE,
    REMEDIATION_TO_VERIFICATION,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_NOT_APPLICABLE,
)
from code.serializer import serialize_steps, sort_steps


class AuditEngine:
    """Evaluates deletion requests against policy and evidence."""

    def __init__(self, identity_resolver: IdentityResolver, evidence_loader: EvidenceLoader):
        self.identity_resolver = identity_resolver
        self.evidence_loader = evidence_loader
        self.classifier = RequestClassifier()

    def audit_case(self, request_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single deletion request.
        
        Returns dict with keys: case_id, deletion_status, steps_json
        """
        case_id = str(request_row["case_id"]).strip()
        email = str(request_row.get("email", "")).strip()
        audit_at = str(request_row.get("audit_at", "")).strip()
        request_text = str(request_row.get("request_text", "")).strip()

        # Step 1: Authorization classification
        is_auth, _ = self.classifier.is_authorized_deletion(request_text)
        if not is_auth:
            return {
                "case_id": case_id,
                "deletion_status": STATUS_NOT_APPLICABLE,
                "steps_json": "[]"
            }

        # Step 2: Resolve user identities
        user_id = self.identity_resolver.resolve_email(email)
        if not user_id:
            # Fallback: if email format matches user_XXX
            if email.startswith("user_"):
                user_id = email
            else:
                return {
                    "case_id": case_id,
                    "deletion_status": STATUS_NOT_APPLICABLE,
                    "steps_json": "[]"
                }

        all_idents = self.identity_resolver.get_all_identifiers(user_id)

        # Step 3: Collect eligible evidence up to audit_at
        eligible_records: List[EvidenceRecord] = []
        for ident in all_idents:
            recs = self.evidence_loader.records_by_user.get(ident, [])
            for r in recs:
                if r.captured_at <= audit_at:
                    eligible_records.append(r)

        # Remove duplicate record references
        seen_keys = set()
        unique_records = []
        for r in eligible_records:
            k = (r.file_id, r.system_id, r.resource_id)
            if k not in seen_keys:
                seen_keys.add(k)
                unique_records.append(r)

        # Step 4: Group by resource to determine latest state at audit_at
        # Sort by captured_at ascending so latest state wins
        unique_records.sort(key=lambda x: x.captured_at)
        resource_latest: Dict[str, EvidenceRecord] = {}
        for r in unique_records:
            resource_latest[r.resource_id] = r

        # Step 5: Evaluate each resource
        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        # Track account_service resources
        account_resources = [r for r in resource_latest.values() if r.system_id == "account_service"]
        
        # If no account resource was explicitly found, infer one if present in lookup or handover
        for r in resource_latest.values():
            sys_id = r.system_id
            res_id = r.resource_id
            cat = r.data_category
            details = r.state_details
            file_id = r.file_id

            # Case A: account_service / USER_PROFILE
            if sys_id == "account_service":
                # Check status
                status_val = details.get("status") or details.get("status_code")
                # 404 or NOT_FOUND indicates deleted
                is_deleted = status_val in [404, "404", "NOT_FOUND", "DELETED", "ABSENT"]
                # If found in read replica or active inventory without 404
                if details.get("raw_sql") and "customer_data_read_replica" in details.get("raw_sql", ""):
                    is_deleted = False
                elif details.get("status") == "FOUND" and "replica" in r.origin:
                    is_deleted = False

                if is_deleted:
                    verifications.append({
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": file_id
                    })
                else:
                    findings.append({
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "account_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case B: search_service / SEARCH_INDEX_ENTRY
            elif sys_id == "search_service":
                # Check if match_found or present
                is_present = (details.get("match_found") is True or 
                              details.get("status") in ["FOUND", "PRESENT"] or
                              "raw_sql" in details or
                              details.get("rows", 0) == 1)
                if is_present:
                    findings.append({
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "search_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case C: export_service / USER_EXPORT
            elif sys_id == "export_service":
                is_present = details.get("status") in ["ACTIVE", "READY", "FOUND", "COMPLETE"] or details.get("download_url") is not None
                if is_present:
                    findings.append({
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "export_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })

            # Case D: support_platform / SUPPORT_MESSAGE or SUPPORT_ATTACHMENT
            elif sys_id == "support_platform":
                if cat == "SUPPORT_ATTACHMENT":
                    findings.append({
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "support_platform",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ""
                    })
                else:
                    # SUPPORT_MESSAGE: rule is REDACT
                    # Check if requester details are exposed
                    has_pii = (details.get("requester_email") is not None or
                               details.get("requester_phone") is not None or
                               details.get("requester_name") is not None or
                               details.get("status") in ["IDENTIFIABLE", "EXPOSED"] or
                               "raw_line" in details and "requester_email=" in details["raw_line"] and "requester_email=null" not in details["raw_line"])
                    if has_pii:
                        findings.append({
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": file_id
                        })
                        remediations.append({
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "REDACT_RECORD",
                            "state": "REDACTED",
                            "evidence_id": ""
                        })
                        verifications.append({
                            "system_id": "support_platform",
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": ""
                        })
                    else:
                        verifications.append({
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
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "REPORT_EXPOSED_PII",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "REDACT_RECORD",
                        "state": "REDACTED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "system_id": "identity_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": file_id
                    })

            # Case F: analytics_platform / ANALYTICS_PROFILE
            elif sys_id == "analytics_platform":
                has_pii = (details.get("customer_reference") is not None or
                           details.get("email") is not None or
                           details.get("phone") is not None or
                           details.get("email_hash") is not None or
                           details.get("status") in ["IDENTIFIABLE", "EXPOSED"] or
                           ("raw_line" in details and "customer_reference=" in details["raw_line"] and "customer_reference=null" not in details["raw_line"]))
                if has_pii:
                    findings.append({
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "REPORT_EXPOSED_PII",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "ANONYMIZE_RECORD",
                        "state": "ANONYMIZED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "analytics_platform",
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ANONYMIZED",
                        "state": "ANONYMIZED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
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
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "REPORT_ACTIVE_DATA_FLOW",
                        "state": "ACTIVE",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "DISABLE_DATA_FLOW",
                        "state": "DISABLED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "system_id": "integration_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": file_id
                    })

            # Case H: backup_service / BACKUP_ARCHIVE
            elif sys_id == "backup_service":
                restore_allowed = details.get("restore_allowed") is True or details.get("status") in ["ALLOWED", "ACTIVE"]
                if restore_allowed:
                    findings.append({
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "REPORT_RESTORE_RISK",
                        "state": "ACTIVE",
                        "evidence_id": file_id
                    })
                    remediations.append({
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "BLOCK_RESTORE",
                        "state": "BLOCKED",
                        "evidence_id": ""
                    })
                    verifications.append({
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": ""
                    })
                else:
                    verifications.append({
                        "system_id": "backup_service",
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": file_id
                    })

            # Case I: security_service / SECURITY_AUDIT_LOG
            elif sys_id == "security_service":
                # Must be retained
                verifications.append({
                    "system_id": "security_service",
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_PRESENT",
                    "state": "PRESENT",
                    "evidence_id": file_id
                })

        # Step 6: Final status decision and step assembly
        # Set phase attribute on all steps
        for f in findings:
            f["phase"] = "FINDING"
        for r in remediations:
            r["phase"] = "REMEDIATION"
        for v in verifications:
            v["phase"] = "VERIFICATION"

        if findings:
            status = STATUS_INCOMPLETE
            # INCOMPLETE cases: findings cite evidence, remediations and future verifications use evidence_id=""
            clean_verifications = []
            for v in verifications:
                v_copy = dict(v)
                v_copy["evidence_id"] = ""
                clean_verifications.append(v_copy)
            all_steps = findings + remediations + clean_verifications
        else:
            status = STATUS_COMPLETE
            all_steps = verifications

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
