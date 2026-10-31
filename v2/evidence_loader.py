"""Multi-modal Evidence Ingestion and Normalization Engine (v2).

Parses, normalizes, and indexes evidence across 94 artifacts spanning:
- JSON snapshot bundles, service resource exports, and customer export jobs
- SQL database dumps (SQLite compatible schemas and read replicas)
- HTTP trace logs and service checkpoint logs (trace-aware event consolidation)
- Pipe-delimited operational handover records
- Document attachments and PDF records
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd

from v2.identity import IdentityResolver


@dataclass
class EvidenceRecord:
    """Normalized evidence record grounded in source files."""
    file_id: str
    origin: str
    captured_at: str
    system_id: str
    resource_id: str
    data_category: str
    state_details: Dict[str, Any]
    user_references: Set[str] = field(default_factory=set)


class EvidenceLoader:
    """Loads, parses, and indexes evidence artifacts from dataset/evidence/."""

    def __init__(self, manifest_path: str = "dataset/evidence_files.csv",
                 base_evidence_dir: str = "dataset"):
        self.manifest_path = manifest_path
        self.base_evidence_dir = base_evidence_dir
        self.all_records: List[EvidenceRecord] = []
        self.records_by_file: Dict[str, List[EvidenceRecord]] = {}
        self.records_by_resource: Dict[str, List[EvidenceRecord]] = {}
        self.records_by_user: Dict[str, List[EvidenceRecord]] = {}

    def _add_record(self, record: EvidenceRecord) -> None:
        self.all_records.append(record)
        self.records_by_file.setdefault(record.file_id, []).append(record)
        self.records_by_resource.setdefault(record.resource_id, []).append(record)
        for u in record.user_references:
            self.records_by_user.setdefault(u, []).append(record)

    def load_all(self, identity_resolver: IdentityResolver) -> None:
        """Parses all evidence artifacts cataloged in evidence_files.csv."""
        manifest_df = pd.read_csv(self.manifest_path)
        for _, row in manifest_df.iterrows():
            file_id = str(row['file_id']).strip()
            file_path = str(row['file_path']).strip()
            origin = str(row.get('origin', '')).strip()
            captured_at = str(row.get('captured_at', '')).strip()

            full_path = os.path.join(self.base_evidence_dir, file_path)
            if not os.path.exists(full_path):
                continue

            ext = os.path.splitext(full_path)[1].lower()
            if ext == '.json':
                self._parse_json(file_id, origin, captured_at, full_path, identity_resolver)
            elif ext == '.txt':
                self._parse_txt(file_id, origin, captured_at, full_path, identity_resolver)
            elif ext in ['.log', '.txt'] and 'log' in file_path.lower():
                self._parse_log(file_id, origin, captured_at, full_path, identity_resolver)
            elif ext == '.log':
                self._parse_log(file_id, origin, captured_at, full_path, identity_resolver)
            elif ext == '.sql':
                self._parse_sql(file_id, origin, captured_at, full_path, identity_resolver)
            elif ext == '.pdf':
                self._parse_pdf(file_id, origin, captured_at, full_path, identity_resolver)

    def _extract_nested_refs(self, obj: Any, urefs_set: Set[str], identity_resolver: IdentityResolver) -> None:
        """Recursively traverses nested dictionaries/lists to extract user identifiers."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    self._extract_nested_refs(v, urefs_set, identity_resolver)
                elif isinstance(v, str):
                    v_str = v.strip().lower()
                    if v_str.startswith("user_") or "@" in v_str:
                        urefs_set.add(v_str)
                        uid = identity_resolver.resolve_email(v_str)
                        if uid:
                            urefs_set.add(uid.lower())
                    elif len(v_str) == 64 and re.match(r'^[a-f0-9]{64}$', v_str):
                        urefs_set.add(v_str)
                        uid = identity_resolver.hash_to_uid.get(v_str)
                        if uid:
                            urefs_set.add(uid.lower())
        elif isinstance(obj, list):
            for elem in obj:
                self._extract_nested_refs(elem, urefs_set, identity_resolver)

    def _parse_json(self, file_id: str, origin: str, captured_at: str,
                    path: str, identity_resolver: IdentityResolver) -> None:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)

        # 1. service_resource_export_*.json
        if "service_exports" in data:
            exports = data["service_exports"]
            for svc_name, svc_data in exports.items():
                if not isinstance(svc_data, dict):
                    continue
                for col_name, items in svc_data.items():
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        res_id = item.get("resource_id")
                        if not res_id:
                            continue

                        urefs = set()
                        self._extract_nested_refs(item, urefs, identity_resolver)

                        cat = "GENERAL"
                        if svc_name == "account_service":
                            cat = "USER_PROFILE"
                        elif svc_name == "analytics_platform":
                            cat = "ANALYTICS_PROFILE"
                        elif svc_name == "backup_service":
                            cat = "BACKUP_ARCHIVE"
                        elif svc_name == "export_service":
                            cat = "USER_EXPORT"
                        elif svc_name == "integration_service":
                            cat = "DATA_FLOW"
                        elif svc_name == "search_service":
                            cat = "SEARCH_INDEX_ENTRY"
                        elif svc_name == "security_service":
                            cat = "SECURITY_AUDIT_LOG"
                        elif svc_name == "support_platform":
                            cat = "SUPPORT_MESSAGE"

                        rec = EvidenceRecord(
                            file_id=file_id,
                            origin=origin,
                            captured_at=captured_at,
                            system_id=svc_name,
                            resource_id=res_id,
                            data_category=cat,
                            state_details=item,
                            user_references=urefs
                        )
                        self._add_record(rec)

        # 2. customer_data_snapshot_bundle_*.json
        elif "snapshots" in data:
            for s in data["snapshots"]:
                col = s.get("collection", "")
                records = s.get("records", [])
                for item in records:
                    if not isinstance(item, dict):
                        continue
                    res_id = item.get("resource_id")
                    if not res_id:
                        continue

                    urefs = set()
                    self._extract_nested_refs(item, urefs, identity_resolver)

                    sys_id = "account_service"
                    cat = "USER_PROFILE"
                    if "tombstone" in res_id or col == "deleted_customer_references":
                        sys_id = "identity_service"
                        cat = "ACCOUNT_TOMBSTONE"
                    elif "audit" in res_id or col == "security_audit_events":
                        sys_id = "security_service"
                        cat = "SECURITY_AUDIT_LOG"
                    elif "analytics" in res_id or col == "analytics_profiles":
                        sys_id = "analytics_platform"
                        cat = "ANALYTICS_PROFILE"
                    elif "support" in res_id or col == "support_tickets":
                        sys_id = "support_platform"
                        cat = "SUPPORT_MESSAGE"

                    rec = EvidenceRecord(
                        file_id=file_id,
                        origin=origin,
                        captured_at=captured_at,
                        system_id=sys_id,
                        resource_id=res_id,
                        data_category=cat,
                        state_details=item,
                        user_references=urefs
                    )
                    self._add_record(rec)

        # 3. Direct JSON jobs/reports (e.g. customer_export_jobs_*.json)
        elif "records" in data and isinstance(data["records"], list):
            col = data.get("collection", "")
            for item in data["records"]:
                if not isinstance(item, dict):
                    continue
                res_id = item.get("resource_id") or item.get("job_id") or item.get("export_id")
                if not res_id:
                    continue
                urefs = set()
                self._extract_nested_refs(item, urefs, identity_resolver)
                sys_id = "export_service" if "export" in res_id else "account_service"
                cat = "USER_EXPORT" if "export" in res_id else "USER_PROFILE"
                rec = EvidenceRecord(
                    file_id=file_id,
                    origin=origin,
                    captured_at=captured_at,
                    system_id=sys_id,
                    resource_id=res_id,
                    data_category=cat,
                    state_details=item,
                    user_references=urefs
                )
                self._add_record(rec)

    def _parse_log(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver: IdentityResolver) -> None:
        traces: Dict[str, Dict[str, Any]] = {}
        standalone_lines: List[Dict[str, Any]] = []

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue

                # Check if line contains a structured JSON payload
                m_json_obj = re.search(r'(\{.*\})', line_str)
                if m_json_obj:
                    try:
                        import json
                        kv_dict = json.loads(m_json_obj.group(1))
                        clean_line = line_str
                        trace_id = kv_dict.get("trace_id") or kv_dict.get("requestId")
                        if not trace_id:
                            m_tr = re.search(r'\b(tr-\d+)\b', line_str)
                            trace_id = m_tr.group(1) if m_tr else None
                    except Exception:
                        m_trace = re.search(r'(?:trace_id|requestId)=([^\s,]+)|\b(tr-\d+)\b', line_str)
                        trace_id = (m_trace.group(1) or m_trace.group(2)).rstrip(',') if m_trace else None
                        clean_line = line_str.replace(r'\"', '"')
                        kv_dict = {}
                        for m_kv in re.finditer(r'(\b[\w_]+)=(?:"([^"]*)"|([^\s,]+))', clean_line):
                            k = m_kv.group(1)
                            v = m_kv.group(2) if m_kv.group(2) is not None else m_kv.group(3)
                            if v.lower() == "true":
                                kv_dict[k] = True
                            elif v.lower() == "false":
                                kv_dict[k] = False
                            elif v.isdigit():
                                kv_dict[k] = int(v)
                            else:
                                kv_dict[k] = v
                else:
                    m_trace = re.search(r'(?:trace_id|requestId)=([^\s,]+)|\b(tr-\d+)\b', line_str)
                    trace_id = (m_trace.group(1) or m_trace.group(2)).rstrip(',') if m_trace else None
                    clean_line = line_str.replace(r'\"', '"')
                    kv_dict = {}
                    for m_kv in re.finditer(r'(\b[\w_]+)=(?:"([^"]*)"|([^\s,]+))', clean_line):
                        k = m_kv.group(1)
                        v = m_kv.group(2) if m_kv.group(2) is not None else m_kv.group(3)
                        if v.lower() == "true":
                            kv_dict[k] = True
                        elif v.lower() == "false":
                            kv_dict[k] = False
                        elif v.isdigit():
                            kv_dict[k] = int(v)
                        else:
                            kv_dict[k] = v

                # Extract user references
                urefs = set()
                for m_u in re.findall(r'\b(user_\d+)\b', clean_line.lower()):
                    urefs.add(m_u)
                for m_e in re.findall(r'[\w\.-]+@[\w\.-]+', clean_line.lower()):
                    urefs.add(m_e)
                    uid = identity_resolver.resolve_email(m_e)
                    if uid:
                        urefs.add(uid.lower())
                for m_h in re.findall(r'\b[a-f0-9]{64}\b', clean_line.lower()):
                    urefs.add(m_h)
                    uid = identity_resolver.hash_to_uid.get(m_h)
                    if uid:
                        urefs.add(uid.lower())

                res_id = kv_dict.get("resource_id")
                sys_id = kv_dict.get("service") or kv_dict.get("function") or kv_dict.get("system") or kv_dict.get("logger")
                if '|' in line_str:
                    parts = [p.strip() for p in line_str.split('|')]
                    if len(parts) >= 4 and not sys_id:
                        sys_id = parts[2]

                entry = {
                    "line": line_str,
                    "kv": kv_dict,
                    "urefs": urefs,
                    "res_id": res_id,
                    "sys_id": sys_id,
                    "trace_id": trace_id
                }

                if trace_id:
                    t_record = traces.setdefault(trace_id, {
                        "urefs": set(),
                        "res_id": None,
                        "sys_id": None,
                        "kv": {},
                        "lines": []
                    })
                    t_record["urefs"].update(urefs)
                    t_record["kv"].update(kv_dict)
                    t_record["lines"].append(line_str)
                    if res_id:
                        t_record["res_id"] = res_id
                    if sys_id:
                        t_record["sys_id"] = sys_id
                else:
                    if res_id:
                        standalone_lines.append(entry)

        # Build records from consolidated traces
        for tr_id, tr in traces.items():
            res_id = tr["res_id"]
            if not res_id:
                continue
            sys_id = tr["sys_id"] or "account_service"
            kv = tr["kv"]

            cat = "GENERAL"
            if "account_" in res_id or sys_id in ["account_service", "account_replica"]:
                sys_id = "account_service"
                cat = "USER_PROFILE"
            elif "audit_" in res_id or sys_id in ["security_service", "security_audit"]:
                sys_id = "security_service"
                cat = "SECURITY_AUDIT_LOG"
            elif "analytics_" in res_id or sys_id in ["analytics_platform", "analytics_service"]:
                sys_id = "analytics_platform"
                cat = "ANALYTICS_PROFILE"
            elif "support_" in res_id or sys_id in ["support_platform", "support_replica"]:
                sys_id = "support_platform"
                cat = "SUPPORT_MESSAGE"
            elif "search_" in res_id or sys_id in ["search_service", "search_replica"]:
                sys_id = "search_service"
                cat = "SEARCH_INDEX_ENTRY"
            elif "data_flow_" in res_id or sys_id in ["integration_service"]:
                sys_id = "integration_service"
                cat = "DATA_FLOW"
            elif "backup_" in res_id or sys_id in ["backup_service"]:
                sys_id = "backup_service"
                cat = "BACKUP_ARCHIVE"

            details = dict(kv)
            details["raw_trace"] = tr["lines"]

            # Derive clean operational status
            h_status = str(kv.get("http_status") or kv.get("status_code") or "")
            rows_val = str(kv.get("rows") if kv.get("rows") is not None else "")
            res_val = str(kv.get("result") or "")
            enabled_val = str(kv.get("enabled")).lower()
            restore_val = str(kv.get("restore_allowed")).lower()
            block_val = str(kv.get("deletion_block")).lower()

            if h_status == "404" or rows_val == "0" or res_val in ["miss", "NOT_FOUND"]:
                details["status"] = "NOT_FOUND"
            elif h_status == "200" or rows_val == "1" or res_val in ["hit", "FOUND"] or kv.get("marker_found") is False or str(kv.get("marker_found")).lower() == "false":
                details["status"] = "FOUND"
            elif enabled_val == "true":
                details["status"] = "ACTIVE"
            elif enabled_val == "false":
                details["status"] = "DISABLED"
            elif restore_val == "true" or block_val == "false":
                details["status"] = "ALLOWED"
                details["restore_allowed"] = True
            elif restore_val == "false" or block_val == "true":
                details["status"] = "BLOCKED"
                details["restore_allowed"] = False

            if kv.get("email_opt_in") is True or str(kv.get("email_opt_in")).lower() == "true":
                details["is_marketing"] = True
                cat = "MARKETING_PROFILE"

            rec = EvidenceRecord(
                file_id=file_id,
                origin=origin,
                captured_at=captured_at,
                system_id=sys_id,
                resource_id=res_id,
                data_category=cat,
                state_details=details,
                user_references=tr["urefs"]
            )
            self._add_record(rec)

        # Build records from standalone lines
        for entry in standalone_lines:
            res_id = entry["res_id"]
            if not res_id:
                continue
            kv = entry["kv"]
            sys_id = entry["sys_id"] or kv.get("system") or kv.get("service") or "account_service"
            cat = kv.get("record_type") or "GENERAL"
            if "account_" in res_id or sys_id in ["account_service", "account_replica"]:
                sys_id = "account_service"
                cat = "USER_PROFILE"
            elif "audit_" in res_id or sys_id in ["security_service", "security_audit"]:
                sys_id = "security_service"
                cat = "SECURITY_AUDIT_LOG"
            elif "analytics_" in res_id or sys_id in ["analytics_platform", "analytics_service"]:
                sys_id = "analytics_platform"
                cat = "ANALYTICS_PROFILE"
            elif "support_" in res_id or sys_id in ["support_platform", "support_replica"]:
                sys_id = "support_platform"
                cat = "SUPPORT_MESSAGE"
            elif "search_" in res_id or sys_id in ["search_service", "search_replica"]:
                sys_id = "search_service"
                cat = "SEARCH_INDEX_ENTRY"
            elif "data_flow_" in res_id or sys_id in ["integration_service"]:
                sys_id = "integration_service"
                cat = "DATA_FLOW"
            elif "backup_" in res_id or sys_id in ["backup_service"]:
                sys_id = "backup_service"
                cat = "BACKUP_ARCHIVE"

            details = dict(kv)
            details["raw_trace"] = [entry["line"]]

            h_status = str(kv.get("http_status") or kv.get("status_code") or "")
            rows_val = str(kv.get("rows") if kv.get("rows") is not None else "")
            res_val = str(kv.get("result") or "")
            enabled_val = str(kv.get("enabled")).lower()
            restore_val = str(kv.get("restore_allowed")).lower()
            block_val = str(kv.get("deletion_block")).lower()

            if h_status == "404" or rows_val == "0" or res_val in ["miss", "NOT_FOUND"]:
                details["status"] = "NOT_FOUND"
            elif h_status == "200" or rows_val == "1" or res_val in ["hit", "FOUND"] or kv.get("marker_found") is False or str(kv.get("marker_found")).lower() == "false":
                details["status"] = "FOUND"
            elif enabled_val == "true":
                details["status"] = "ACTIVE"
            elif enabled_val == "false":
                details["status"] = "DISABLED"
            elif restore_val == "true" or block_val == "false":
                details["status"] = "ALLOWED"
                details["restore_allowed"] = True
            elif restore_val == "false" or block_val == "true":
                details["status"] = "BLOCKED"
                details["restore_allowed"] = False

            if kv.get("email_opt_in") is True or str(kv.get("email_opt_in")).lower() == "true":
                details["is_marketing"] = True
                cat = "MARKETING_PROFILE"

            rec = EvidenceRecord(
                file_id=file_id,
                origin=origin,
                captured_at=captured_at,
                system_id=sys_id,
                resource_id=res_id,
                data_category=cat,
                state_details=details,
                user_references=entry["urefs"]
            )
            self._add_record(rec)

    def _parse_sql(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver: IdentityResolver) -> None:
        import json
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if not line.startswith("INSERT INTO"):
                    continue

                m_table = re.search(r"INSERT INTO\s+[\"']?(\w+)[\"']?", line, re.IGNORECASE)
                table_name = m_table.group(1).lower() if m_table else ""

                m_res = re.search(r"[\"'](account_\d+|search_\d+|analytics_\d+|support_\d+|audit_record_\d+|backup_\d+|data_flow_\d+|export_\d+|tombstone_\d+)[\"']", line)
                if not m_res:
                    continue
                res_id = m_res.group(1)

                urefs = set()
                for m_u in re.findall(r"\b(user_\d+)\b", line.lower()):
                    urefs.add(m_u)
                for m_e in re.findall(r"[\w\.-]+@[\w\.-]+", line.lower()):
                    urefs.add(m_e)
                    uid = identity_resolver.resolve_email(m_e)
                    if uid:
                        urefs.add(uid.lower())
                for m_h in re.findall(r"\b[a-f0-9]{64}\b", line.lower()):
                    urefs.add(m_h)
                    uid = identity_resolver.hash_to_uid.get(m_h)
                    if uid:
                        urefs.add(uid.lower())

                sys_id = "account_service"
                cat = "USER_PROFILE"
                if "account_" in res_id:
                    sys_id = "account_service"
                    cat = "USER_PROFILE"
                elif "search_" in res_id:
                    sys_id = "search_service"
                    cat = "SEARCH_INDEX_ENTRY"
                elif "analytics_" in res_id:
                    sys_id = "analytics_platform"
                    cat = "ANALYTICS_PROFILE"
                elif "support_" in res_id:
                    sys_id = "support_platform"
                    cat = "SUPPORT_MESSAGE"
                elif "audit_record_" in res_id:
                    sys_id = "security_service"
                    cat = "SECURITY_AUDIT_LOG"
                elif "backup_" in res_id:
                    sys_id = "backup_service"
                    cat = "BACKUP_ARCHIVE"
                elif "data_flow_" in res_id:
                    sys_id = "integration_service"
                    cat = "DATA_FLOW"
                elif "export_" in res_id:
                    sys_id = "export_service"
                    cat = "USER_EXPORT"
                elif "tombstone_" in res_id:
                    sys_id = "identity_service"
                    cat = "ACCOUNT_TOMBSTONE"

                details = {"raw_sql": line.strip(), "table": table_name}

                # Extract JSON payload if present in SQL line
                m_json = re.search(r"(\{.*\})", line)
                if m_json:
                    try:
                        payload = json.loads(m_json.group(1))
                        details.update(payload)
                        self._extract_nested_refs(payload, urefs, identity_resolver)
                        if "service" in payload:
                            sys_id = payload["service"]
                        if "subject_reference" in payload and payload["subject_reference"]:
                            urefs.add(payload["subject_reference"].lower())
                    except Exception:
                        pass

                if "backup_restore_entries" in table_name:
                    sys_id = "backup_service"
                    cat = "BACKUP_ARCHIVE"
                    m_args = re.search(r"VALUES\s*\((.*)\);?", line, re.IGNORECASE)
                    if m_args:
                        args = [a.strip().strip("'") for a in m_args.group(1).split(',')]
                        if len(args) >= 5 and args[4] in ['1', 1, 'true', 'TRUE']:
                            details["restore_allowed"] = True
                            details["status"] = "ALLOWED"
                        else:
                            details["restore_allowed"] = False
                            details["status"] = "BLOCKED"

                elif "connector_subscriptions" in table_name:
                    sys_id = "integration_service"
                    cat = "DATA_FLOW"
                    m_args = re.search(r"VALUES\s*\((.*)\);?", line, re.IGNORECASE)
                    if m_args:
                        args = [a.strip().strip("'") for a in m_args.group(1).split(',')]
                        if len(args) >= 5 and args[4] in ['1', 1, 'true', 'TRUE']:
                            details["enabled"] = True
                            details["status"] = "ACTIVE"
                        else:
                            details["enabled"] = False
                            details["status"] = "DISABLED"

                elif "customer_search_documents" in table_name:
                    sys_id = "search_service"
                    cat = "SEARCH_INDEX_ENTRY"
                    details["status"] = "FOUND"
                    details["match_found"] = True

                elif "customer_exports" in table_name:
                    sys_id = "export_service"
                    cat = "USER_EXPORT"
                    details["status"] = "FOUND"

                elif "support_records" in table_name:
                    sys_id = "support_platform"
                    cat = "SUPPORT_MESSAGE"
                    m_val = re.findall(r"'([^']*)'", line)
                    has_pii = any("@" in v for v in m_val) or any(v.startswith("+") for v in m_val)
                    details["status"] = "EXPOSED" if has_pii else "REDACTED"

                elif "security_audit_records" in table_name:
                    sys_id = "security_service"
                    cat = "SECURITY_AUDIT_LOG"
                    details["status"] = "PRESENT"

                else:
                    if "account_" in res_id:
                        sys_id = "account_service"
                        cat = "USER_PROFILE"
                        details["status"] = "FOUND"

                rec = EvidenceRecord(
                    file_id=file_id,
                    origin=origin,
                    captured_at=captured_at,
                    system_id=sys_id,
                    resource_id=res_id,
                    data_category=cat,
                    state_details=details,
                    user_references=urefs
                )
                self._add_record(rec)

    def _parse_txt(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver: IdentityResolver) -> None:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith('#'):
                    continue
                if '|' in line_str:
                    parts = [p.strip() for p in line_str.lstrip('-').split('|')]
                    if len(parts) >= 6:
                        ts, sys_id, res_id, cat, status, ident = parts[:6]
                        urefs = {ident.lower()}
                        uid = identity_resolver.resolve_email(ident.lower()) or (ident.lower() if ident.lower().startswith('user_') else None)
                        if uid:
                            urefs.add(uid.lower())

                        details = {
                            "status": status,
                            "category": cat,
                            "identifier": ident,
                            "timestamp": ts
                        }
                        rec = EvidenceRecord(
                            file_id=file_id,
                            origin=origin,
                            captured_at=captured_at,
                            system_id=sys_id,
                            resource_id=res_id,
                            data_category=cat,
                            state_details=details,
                            user_references=urefs
                        )
                        self._add_record(rec)

    def _parse_pdf(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver: IdentityResolver) -> None:
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            full_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"

            # Check if this is a statutory register
            if "legal_retention_register" in path.lower() or "disputed orders and tax" in full_text.lower():
                return

            urefs = set()
            for m_u in re.findall(r'user_\d+', full_text.lower()):
                urefs.add(m_u)
            for m_e in re.findall(r'[\w\.-]+@[\w\.-]+', full_text.lower()):
                urefs.add(m_e)
                uid = identity_resolver.resolve_email(m_e)
                if uid:
                    urefs.add(uid.lower())

            for name, uid in identity_resolver.name_to_uid.items():
                if len(name) >= 4 and name in full_text.lower():
                    urefs.add(name)
                    urefs.add(uid.lower())

            m_res = re.search(r'(account_\d+|support_\d+|audit_record_\d+|audit_\d+|export_\d+|data_flow_\d+|backup_\d+|tombstone_\d+)', full_text)
            if m_res:
                res_id = m_res.group(1)
            else:
                m_nst = re.search(r'NST-\d{4}-\d{4}-(\d+)', full_text)
                if m_nst:
                    res_id = f"export_{m_nst.group(1)}"
                else:
                    res_id = f"support_{file_id.split('_')[1]}"

            sys_id = "support_platform"
            cat = "SUPPORT_MESSAGE"
            if "export_" in res_id:
                sys_id = "export_service"
                cat = "USER_EXPORT"
            elif "audit_" in res_id:
                sys_id = "security_service"
                cat = "SECURITY_AUDIT_LOG"
            elif "account_" in res_id:
                sys_id = "account_service"
                cat = "USER_PROFILE"

            rec = EvidenceRecord(
                file_id=file_id,
                origin=origin,
                captured_at=captured_at,
                system_id=sys_id,
                resource_id=res_id,
                data_category=cat,
                state_details={"extracted_text": full_text[:500], "status": "FOUND"},
                user_references=urefs
            )
            self._add_record(rec)
        except Exception:
            pass

