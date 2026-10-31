"""Step sorting and serialization module for Ghost Data Still Exists.

Ensures strict compliance with challenge output contract:
- Exactly 7 keys per step: step_no, phase, system_id, resource_id, operation, state, evidence_id
- Canonical phase order: FINDING -> REMEDIATION -> VERIFICATION
- Strict internal operation order per phase
- Secondary sorting by system_id ascending, then resource_id ascending
- Consecutive 1-indexed step numbers
- Valid JSON array serialization
"""

import json
from typing import Any, Dict, List
import pandas as pd

from code.policy import (
    FINDING_OPERATIONS,
    PHASE_FINDING,
    PHASE_ORDER,
    PHASE_REMEDIATION,
    PHASE_VERIFICATION,
    REMEDIATION_OPERATIONS,
    VERIFICATION_OPERATIONS,
)


def sort_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sorts steps according to canonical challenge rules."""
    def sort_key(s: Dict[str, Any]):
        phase = s.get("phase", "")
        p_idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else 999
        
        op = s.get("operation", "")
        if phase == PHASE_FINDING:
            op_idx = FINDING_OPERATIONS.index(op) if op in FINDING_OPERATIONS else 999
        elif phase == PHASE_REMEDIATION:
            op_idx = REMEDIATION_OPERATIONS.index(op) if op in REMEDIATION_OPERATIONS else 999
        elif phase == PHASE_VERIFICATION:
            op_idx = VERIFICATION_OPERATIONS.index(op) if op in VERIFICATION_OPERATIONS else 999
        else:
            op_idx = 999

        sys_id = str(s.get("system_id", ""))
        res_id = str(s.get("resource_id", ""))
        return (p_idx, op_idx, sys_id, res_id)

    sorted_list = sorted(steps, key=sort_key)
    
    # Renumber consecutively from 1 and format strictly with 7 keys
    formatted = []
    for idx, s in enumerate(sorted_list, 1):
        formatted.append({
            "step_no": idx,
            "phase": s["phase"],
            "system_id": s["system_id"],
            "resource_id": s["resource_id"],
            "operation": s["operation"],
            "state": s["state"],
            "evidence_id": s.get("evidence_id", "") or "",
        })
    return formatted


def serialize_steps(steps: List[Dict[str, Any]]) -> str:
    """Serializes step list into a valid JSON string."""
    canonical = sort_steps(steps)
    return json.dumps(canonical, ensure_ascii=False)


def save_output_csv(rows: List[Dict[str, Any]], output_path: str = "output.csv") -> None:
    """
    Writes the final output.csv strictly sorted by case_id.
    Columns: case_id, deletion_status, steps_json
    """
    df = pd.DataFrame(rows)
    
    # Ensure correct columns and sort order
    required_cols = ["case_id", "deletion_status", "steps_json"]
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"Rows missing required columns: {required_cols}")

    df = df[required_cols]
    
    # Sort by case_id using numeric extraction if formatted like case_XX
    def case_sort_key(cid: str):
        cid_str = str(cid)
        parts = cid_str.split("_")
        if len(parts) == 2 and parts[1].isdigit():
            return int(parts[1])
        return cid_str

    df["_sort_key"] = df["case_id"].apply(case_sort_key)
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"]).reset_index(drop=True)
    
    df.to_csv(output_path, index=False, encoding="utf-8")
