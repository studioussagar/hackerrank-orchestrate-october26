"""Deletion policy, enums, and ordering definitions for Ghost Data Still Exists.

Encodes operations, phases, states, and deletion rules defined in
deletion_rules.csv and AGENTS.md §6.4.
"""

from typing import Dict, List, Optional
import pandas as pd


# Allowed status values
STATUS_COMPLETE = "COMPLETE"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"
ALLOWED_STATUSES = {STATUS_COMPLETE, STATUS_INCOMPLETE, STATUS_NOT_APPLICABLE}

# Allowed phases
PHASE_FINDING = "FINDING"
PHASE_REMEDIATION = "REMEDIATION"
PHASE_VERIFICATION = "VERIFICATION"
PHASE_ORDER = [PHASE_FINDING, PHASE_REMEDIATION, PHASE_VERIFICATION]

# Canonical operation ordering per phase
FINDING_OPERATIONS = [
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
]

REMEDIATION_OPERATIONS = [
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
]

VERIFICATION_OPERATIONS = [
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
]

# Mapping operation to required state
OPERATION_TO_STATE: Dict[str, str] = {
    # Findings
    "REPORT_REMAINING_RECORD": "PRESENT",
    "REPORT_EXPOSED_PII": "PRESENT",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE",
    "REPORT_RESTORE_RISK": "ACTIVE",
    # Remediation
    "DISABLE_DATA_FLOW": "DISABLED",
    "BLOCK_RESTORE": "BLOCKED",
    "DELETE_RECORD": "ABSENT",
    "REDACT_RECORD": "REDACTED",
    "ANONYMIZE_RECORD": "ANONYMIZED",
    # Verification
    "VERIFY_RECORD_ABSENT": "ABSENT",
    "VERIFY_RECORD_PRESENT": "PRESENT",
    "VERIFY_RECORD_REDACTED": "REDACTED",
    "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
    "VERIFY_RESTORE_BLOCKED": "BLOCKED",
}

# Finding operation to proposed remediation and post-remediation verification
FINDING_TO_REMEDIATION: Dict[str, str] = {
    "REPORT_REMAINING_RECORD": "DELETE_RECORD",
    "REPORT_EXPOSED_PII": "REDACT_RECORD",  # or ANONYMIZE_RECORD depending on rule
    "REPORT_ACTIVE_DATA_FLOW": "DISABLE_DATA_FLOW",
    "REPORT_RESTORE_RISK": "BLOCK_RESTORE",
}

REMEDIATION_TO_VERIFICATION: Dict[str, str] = {
    "DELETE_RECORD": "VERIFY_RECORD_ABSENT",
    "REDACT_RECORD": "VERIFY_RECORD_REDACTED",
    "ANONYMIZE_RECORD": "VERIFY_RECORD_ANONYMIZED",
    "DISABLE_DATA_FLOW": "VERIFY_DATA_FLOW_DISABLED",
    "BLOCK_RESTORE": "VERIFY_RESTORE_BLOCKED",
}


class PolicyEngine:
    """Manages policy rules from deletion_rules.csv."""

    def __init__(self, rules_path: str = "dataset/deletion_rules.csv"):
        self.rules_df = pd.read_csv(rules_path)
        self.category_to_action: Dict[str, str] = {}
        for _, r in self.rules_df.iterrows():
            cat = str(r['data_category']).strip()
            act = str(r['required_action']).strip()
            self.category_to_action[cat] = act

    def get_required_action(self, data_category: str) -> str:
        """Returns DELETE, REDACT, ANONYMIZE, or RETAIN."""
        return self.category_to_action.get(data_category, "DELETE")
