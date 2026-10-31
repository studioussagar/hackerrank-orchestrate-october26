"""Identity resolution module for Ghost Data Still Exists.

Reconstructs current and historical user identities from user_identities.csv
and user_audit_log.csv, handling case-insensitive email matching, phone numbers,
email hashes, and name changes.
"""

from typing import Dict, Optional, Set
import pandas as pd


class IdentityResolver:
    """Resolves requests and evidence records to stable user identities."""

    def __init__(self, identities_path: str = "dataset/user_identities.csv",
                 audit_log_path: str = "dataset/user_audit_log.csv"):
        self.identities_df = pd.read_csv(identities_path)
        self.audit_log_df = pd.read_csv(audit_log_path)
        
        self.email_to_uid: Dict[str, str] = {}
        self.name_to_uid: Dict[str, str] = {}
        self.hash_to_uid: Dict[str, str] = {}
        self.uid_to_profile: Dict[str, dict] = {}
        self.uid_to_emails: Dict[str, Set[str]] = {}
        self.uid_to_phones: Dict[str, Set[str]] = {}
        self.uid_to_names: Dict[str, Set[str]] = {}
        self.uid_to_hashes: Dict[str, Set[str]] = {}
        self.uid_to_all_identifiers: Dict[str, Set[str]] = {}
        
        self._build_index()

    def _build_index(self) -> None:
        """Indexes user records and historical changes."""
        for _, row in self.identities_df.iterrows():
            uid = str(row['user_id']).strip()
            self.uid_to_profile[uid] = row.to_dict()
            
            emails = set()
            phones = set()
            names = set()
            hashes = set()
            all_idents = {uid.lower()}
            
            if pd.notna(row.get('email')):
                e = str(row['email']).strip().lower()
                emails.add(e)
                all_idents.add(e)
                self.email_to_uid[e] = uid
                
            if pd.notna(row.get('phone')):
                p = str(row['phone']).strip().lower()
                phones.add(p)
                all_idents.add(p)
                
            if pd.notna(row.get('name')):
                n = str(row['name']).strip().lower()
                names.add(n)
                all_idents.add(n)
                self.name_to_uid[n] = uid
                
            if pd.notna(row.get('email_hash')):
                h = str(row['email_hash']).strip().lower()
                hashes.add(h)
                all_idents.add(h)
                self.hash_to_uid[h] = uid
                
            self.uid_to_emails[uid] = emails
            self.uid_to_phones[uid] = phones
            self.uid_to_names[uid] = names
            self.uid_to_hashes[uid] = hashes
            self.uid_to_all_identifiers[uid] = all_idents

        # Ingest historical audit log changes
        for _, row in self.audit_log_df.iterrows():
            uid = str(row['user_id']).strip()
            if uid not in self.uid_to_all_identifiers:
                self.uid_to_all_identifiers[uid] = {uid.lower()}
                self.uid_to_emails[uid] = set()
                self.uid_to_phones[uid] = set()
                self.uid_to_names[uid] = set()
                self.uid_to_hashes[uid] = set()

            field = str(row.get('field_name', '')).strip().lower()
            old_val = str(row['old_value']).strip() if pd.notna(row.get('old_value')) else None
            new_val = str(row['new_value']).strip() if pd.notna(row.get('new_value')) else None

            for val in [old_val, new_val]:
                if not val:
                    continue
                v_lower = val.lower()
                self.uid_to_all_identifiers[uid].add(v_lower)
                if field == 'email':
                    self.uid_to_emails[uid].add(v_lower)
                    self.email_to_uid[v_lower] = uid
                elif field == 'phone':
                    self.uid_to_phones[uid].add(v_lower)
                elif field == 'name':
                    self.uid_to_names[uid].add(v_lower)
                    self.name_to_uid[v_lower] = uid
                elif field == 'email_hash':
                    self.uid_to_hashes[uid].add(v_lower)
                    self.hash_to_uid[v_lower] = uid

    def resolve_email(self, email: str) -> Optional[str]:
        """Resolves an email address (current or historical) to a user_id."""
        if not email:
            return None
        return self.email_to_uid.get(str(email).strip().lower())

    def resolve_name(self, name: str) -> Optional[str]:
        """Resolves a user name (current or historical) to a user_id."""
        if not name:
            return None
        return self.name_to_uid.get(str(name).strip().lower())

    def get_all_identifiers(self, user_id: str) -> Set[str]:
        """Returns all lowercase identifier strings for the user."""
        return self.uid_to_all_identifiers.get(user_id, set())

    def get_known_emails(self, user_id: str) -> Set[str]:
        """Returns all known emails for the user."""
        return self.uid_to_emails.get(user_id, set())

    def get_known_phones(self, user_id: str) -> Set[str]:
        """Returns all known phones for the user."""
        return self.uid_to_phones.get(user_id, set())

    def get_known_names(self, user_id: str) -> Set[str]:
        """Returns all known names for the user."""
        return self.uid_to_names.get(user_id, set())

    def get_known_hashes(self, user_id: str) -> Set[str]:
        """Returns all known email hashes for the user."""
        return self.uid_to_hashes.get(user_id, set())

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Returns the current profile snapshot for the user."""
        return self.uid_to_profile.get(user_id)
