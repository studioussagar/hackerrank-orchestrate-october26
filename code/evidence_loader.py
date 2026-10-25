"""Evidence loader and indexer module for Ghost Data Still Exists.

Parses all evidence files from dataset/evidence_files.csv and dataset/evidence/,
indexing observed resource states by user_id and resource_id.
"""

import glob
import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set
import pandas as pd


class EvidenceRecord:
    """Represents a single resource state observation from an evidence file."""

    def __init__(self, file_id: str, origin: str, captured_at: str,
                 system_id: str, resource_id: str, data_category: str,
                 state_details: Dict[str, Any], user_references: Set[str]):
        self.file_id = file_id
        self.origin = origin
        self.captured_at = captured_at
        self.system_id = system_id
        self.resource_id = resource_id
        self.data_category = data_category
        self.state_details = state_details
        self.user_references = user_references  # set of lowercase user_ids/emails/identifiers

    def __repr__(self) -> str:
        return (f"<EvidenceRecord file={self.file_id} sys={self.system_id} "
                f"res={self.resource_id} cat={self.data_category} cap={self.captured_at}>")


class EvidenceLoader:
    """Loads and indexes evidence from dataset/evidence_files.csv."""

    def __init__(self, manifest_path: str = "dataset/evidence_files.csv",
                 base_evidence_dir: str = "dataset"):
        self.manifest_df = pd.read_csv(manifest_path)
        self.base_evidence_dir = base_evidence_dir
        self.file_manifest: Dict[str, dict] = {}
        for _, r in self.manifest_df.iterrows():
            self.file_manifest[r['file_id']] = r.to_dict()

        # Indexes
        self.records_by_user: Dict[str, List[EvidenceRecord]] = {}
        self.records_by_resource: Dict[str, List[EvidenceRecord]] = {}
        self.records_by_file: Dict[str, List[EvidenceRecord]] = {}
        self.all_records: List[EvidenceRecord] = []

    def load_all(self, identity_resolver) -> None:
        """Parses all evidence files and indexes observations."""
        for file_id, meta in self.file_manifest.items():
            rel_path = meta['file_path']
            full_path = os.path.join(self.base_evidence_dir, rel_path)
            if not os.path.exists(full_path):
                # Try relative to repo root
                full_path = rel_path
                if not os.path.exists(full_path):
                    continue

            origin = meta.get('origin', '')
            captured_at = meta.get('captured_at', '')

            try:
                if rel_path.endswith('.json'):
                    self._parse_json(file_id, origin, captured_at, full_path, identity_resolver)
                elif rel_path.endswith('.txt'):
                    self._parse_txt(file_id, origin, captured_at, full_path, identity_resolver)
                elif rel_path.endswith('.log'):
                    self._parse_log(file_id, origin, captured_at, full_path, identity_resolver)
                elif rel_path.endswith('.sql'):
                    self._parse_sql(file_id, origin, captured_at, full_path, identity_resolver)
                elif rel_path.endswith('.pdf'):
                    self._parse_pdf(file_id, origin, captured_at, full_path, identity_resolver)
            except Exception as e:
                # Log or ignore parsing error for corrupted test fixture
                pass

    def _add_record(self, record: EvidenceRecord) -> None:
        self.all_records.append(record)
        self.records_by_file.setdefault(record.file_id, []).append(record)
        self.records_by_resource.setdefault(record.resource_id, []).append(record)
        for u in record.user_references:
            self.records_by_user.setdefault(u, []).append(record)

    def _parse_json(self, file_id: str, origin: str, captured_at: str,
                    path: str, identity_resolver) -> None:
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

                        # Extract user reference
                        urefs = set()
                        for key in ["customer_reference", "subject_reference", "user_id", "customer_email", "requester_email", "query_key"]:
                            val = item.get(key)
                            if val:
                                v_str = str(val).strip().lower()
                                urefs.add(v_str)
                                uid = identity_resolver.resolve_email(v_str)
                                if uid:
                                    urefs.add(uid.lower())

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
                    for key in ["customer_reference", "subject_reference", "user_id", "email", "requester_email"]:
                        val = item.get(key)
                        if val:
                            v_str = str(val).strip().lower()
                            urefs.add(v_str)
                            uid = identity_resolver.resolve_email(v_str)
                            if uid:
                                urefs.add(uid.lower())

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

        # 3. Direct JSON jobs/reports (e.g. export_jobs, analytics_report, etc.)
        else:
            # Handle other specific JSON schemas
            items = data if isinstance(data, list) else data.get("jobs", data.get("connectors", data.get("records", [])))
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    res_id = item.get("resource_id") or item.get("job_id") or item.get("export_id")
                    if not res_id:
                        continue
                    urefs = set()
                    for key in ["customer_reference", "user_id", "email", "customer_email"]:
                        val = item.get(key)
                        if val:
                            v_str = str(val).strip().lower()
                            urefs.add(v_str)
                            uid = identity_resolver.resolve_email(v_str)
                            if uid:
                                urefs.add(uid.lower())

                    sys_id = "export_service" if "export" in res_id else "analytics_platform"
                    cat = "USER_EXPORT" if "export" in res_id else "ANALYTICS_PROFILE"
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

    def _parse_txt(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver) -> None:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith('#'):
                    continue
                if '|' in line_str:
                    parts = [p.strip() for p in line_str.lstrip('-').split('|')]
                    if len(parts) >= 6:
                        # timestamp | system_id | resource_id | category | status | identifier
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

    def _parse_log(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver) -> None:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if not line.strip():
                    continue
                
                # Check for key-value logging: resource_id=...
                m_res = re.search(r'resource_id=([^\s]+)', line)
                if not m_res:
                    continue
                res_id = m_res.group(1).rstrip(',')

                m_sys = re.search(r'service=([^\s]+)', line) or re.search(r'logger=([^\s]+)', line)
                sys_id = m_sys.group(1).rstrip(',') if m_sys else "account_service"

                urefs = set()
                m_key = re.search(r'lookup_key=([^\s]+)', line) or re.search(r'subject_reference=([^\s]+)', line) or re.search(r'customer_reference=([^\s]+)', line)
                if m_key:
                    k = m_key.group(1).strip().lower()
                    if k != "null":
                        urefs.add(k)
                        uid = identity_resolver.resolve_email(k) or (k if k.startswith('user_') else None)
                        if uid:
                            urefs.add(uid.lower())

                # Also search for any user_XXX or emails in the log line
                for m_u in re.findall(r'user_\d+', line.lower()):
                    urefs.add(m_u)
                for m_e in re.findall(r'[\w\.-]+@[\w\.-]+', line.lower()):
                    urefs.add(m_e)
                    uid = identity_resolver.resolve_email(m_e)
                    if uid:
                        urefs.add(uid.lower())

                # Determine category and state
                cat = "GENERAL"
                if "account_" in res_id or sys_id == "account_service":
                    cat = "USER_PROFILE"
                elif "audit_" in res_id or sys_id == "security_service":
                    cat = "SECURITY_AUDIT_LOG"
                elif "analytics_" in res_id or sys_id == "analytics_platform":
                    cat = "ANALYTICS_PROFILE"
                elif "support_" in res_id or sys_id == "support_platform":
                    cat = "SUPPORT_MESSAGE"
                elif "search_" in res_id or sys_id == "search_service":
                    cat = "SEARCH_INDEX_ENTRY"
                elif "data_flow_" in res_id or sys_id == "integration_service":
                    cat = "DATA_FLOW"
                elif "backup_" in res_id or sys_id == "backup_service":
                    cat = "BACKUP_ARCHIVE"

                details = {"raw_line": line.strip()}
                if "http_status=404" in line or "rows=0" in line or "NOT_FOUND" in line:
                    details["status"] = "NOT_FOUND"
                elif "rows=1" in line or "http_status=200" in line or "FOUND" in line:
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

    def _parse_sql(self, file_id: str, origin: str, captured_at: str,
                   path: str, identity_resolver) -> None:
        # Ingest SQL insert statements
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if not line.startswith("INSERT INTO"):
                    continue
                # Extract resource_id and user references
                m_res = re.search(r"'(account_\d+|search_\d+|analytics_\d+|support_\d+|audit_record_\d+|backup_\d+|data_flow_\d+|export_\d+|tombstone_\d+)'", line)
                if not m_res:
                    continue
                res_id = m_res.group(1)

                urefs = set()
                for m_u in re.findall(r"'(user_\d+)'", line.lower()):
                    urefs.add(m_u)
                for m_e in re.findall(r"[\w\.-]+@[\w\.-]+", line.lower()):
                    urefs.add(m_e)
                    uid = identity_resolver.resolve_email(m_e)
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
                elif "audit_" in res_id:
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

                details = {"raw_sql": line.strip(), "status": "FOUND"}
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
                   path: str, identity_resolver) -> None:
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            full_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"

            urefs = set()
            for m_u in re.findall(r'user_\d+', full_text.lower()):
                urefs.add(m_u)
            for m_e in re.findall(r'[\w\.-]+@[\w\.-]+', full_text.lower()):
                urefs.add(m_e)
                uid = identity_resolver.resolve_email(m_e)
                if uid:
                    urefs.add(uid.lower())

            # Match any known customer names from identities
            for name, uid in identity_resolver.name_to_uid.items():
                if len(name) >= 4 and name in full_text.lower():
                    urefs.add(name)
                    urefs.add(uid.lower())

            # Extract resource_id
            m_res = re.search(r'(support_\d+|account_\d+|audit_record_\d+)', full_text)
            res_id = m_res.group(1) if m_res else "support_001"

            rec = EvidenceRecord(
                file_id=file_id,
                origin=origin,
                captured_at=captured_at,
                system_id="support_platform",
                resource_id=res_id,
                data_category="SUPPORT_ATTACHMENT" if "attachment" in path.lower() else "SUPPORT_MESSAGE",
                state_details={"full_text": full_text[:200], "status": "FOUND"},
                user_references=urefs
            )
            self._add_record(rec)
        except Exception:
            pass
