# Ghost Data Still Exists: Evaluation Report

## 1. Executive Summary

This report evaluates the performance of the **Ghost Data Still Exists** AI deletion-audit agent.
The audit engine reconstructs user identity graphs, ingests multi-modal evidence (JSON snapshot bundles,
SQL read replicas, readback trace logs, handover records, PDFs, and diagnostic logs), enforces strict
`audit_at` temporal boundaries, and applies `deletion_rules.csv` policies to determine whether platform deletions
are complete, incomplete, or not applicable.

### Overall Benchmark Metrics (Public Ground Truth: 32 Cases)

| Metric | Score | Matches / Total | Description |
|---|---|---|---|
| **Case-Level Status Accuracy** | **65.6%** | 21 / 32 | Exact match on `deletion_status` (`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`) |
| **Field-Level Step Accuracy** | **28.0%** | 272 / 970 | Exact match across `phase`, `system_id`, `resource_id`, `operation`, `state` |
| **Exact Sequence Accuracy** | **12.5%** | 4 / 32 | Exact end-to-end match of canonical step ordering and contents |

---

## 2. Confusion Matrix (Deletion Status)

| Ground Truth \ Prediction | COMPLETE | INCOMPLETE | NOT_APPLICABLE |
|---|---|---|---|
| **COMPLETE** | 9 | 1 | 0 |
| **INCOMPLETE** | 10 | 12 | 0 |
| **NOT_APPLICABLE** | 0 | 0 | 0 |

---

## 3. Synthetic Participant Evaluation Cases

As required by challenge contract §6.8, three synthetic evaluation test cases were designed, executed, and verified:

### Synthetic Case 1: Replication Drift with Active Synchronization Risk (`case_syn_01`)
- **Scenario:** The user requested deletion. The primary database deleted `account_8812`, but an un-synced read replica (`customer_data_read_replica`) still retained the profile. Furthermore, an active data flow (`data_flow_4190`) is configured to re-sync profiles every 6 hours.
- **Expected Outcome:** `INCOMPLETE`.
- **Finding Steps:**
  1. `REPORT_REMAINING_RECORD` on `account_service:account_8812` (State: `PRESENT`).
  2. `REPORT_ACTIVE_DATA_FLOW` on `integration_service:data_flow_4190` (State: `ACTIVE`).
- **Remediation Order:**
  1. `DISABLE_DATA_FLOW` on `data_flow_4190` (Disabled before data modifications).
  2. `DELETE_RECORD` on `account_8812`.
- **Verification:** Both verified absent/disabled with empty `evidence_id`.
- **Result:** **PASSED**.

### Synthetic Case 2: Lawful Retention & Account Tombstone Hygiene (`case_syn_02`)
- **Scenario:** The user requested erasure. All primary and secondary profiles, search indexes, and caches were deleted. A security audit log (`audit_record_1109`) is retained under the 7-year statutory retention rule (`rule_12`). An account tombstone (`tombstone_771`) preserves only the internal UUID reference, with all direct PII (name, email, phone, email hash) purged.
- **Expected Outcome:** `COMPLETE`.
- **Verification Steps:**
  1. `VERIFY_RECORD_ABSENT` on `account_service:account_1092` (State: `ABSENT`).
  2. `VERIFY_RECORD_PRESENT` on `security_service:audit_record_1109` (State: `PRESENT`).
  3. `VERIFY_RECORD_REDACTED` on `identity_service:tombstone_771` (State: `REDACTED`).
- **Result:** **PASSED**.

### Synthetic Case 3: Ambiguous Multi-Lingual Non-Deletion Intent (`case_syn_03`)
- **Scenario:** A user submitted a message in French requesting a copy of data under GDPR Article 15: *"Je vous écris pour demander une copie complète de mes données personnelles. Je ne demande pas la suppression de mon compte pour le moment; veuillez laisser le compte actif."*
- **Expected Outcome:** `NOT_APPLICABLE` with `steps_json=[]`.
- **Result:** **PASSED**. The intent classifier correctly recognized the non-deletion condition and suppressed destructive audit steps.

---

## 4. Failures Found and Engineering Improvements Made

1. **Replication Drift Discovery:**
   - *Failure:* Early audits trusted `reported_status: COMPLETE` when the primary profile was deleted, missing copies residing in asynchronous read replicas (`customer_data_read_replica_*.sql`).
   - *Improvement:* Implemented cross-replica snapshot diffing up to `audit_at`.
2. **Canonical Step Sequence Invariants:**
   - *Failure:* Remediations were initially generated before data flows were disabled, violating the dependency order rule that upstream sync pipelines must be blocked before downstream copies are altered.
   - *Improvement:* Enforced strict canonical sorting: `DISABLE_DATA_FLOW` < `BLOCK_RESTORE` < `DELETE_RECORD` < `REDACT_RECORD` < `ANONYMIZE_RECORD`.
3. **Temporal Cutoff Strictness:**
   - *Failure:* Evidence collected after `audit_at` occasionally leaked into findings when sorting manifests without filtering by `captured_at <= audit_at`.
   - *Improvement:* Centralized temporal filtering in `EvidenceLoader` and `AuditEngine` ensuring zero post-cutoff data contamination.
