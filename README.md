# HackerRank Orchestrate - October 2026: Ghost Data Still Exists

An AI-powered deletion-audit agent that independently verifies whether personal data was truly deleted across commerce platform systems, replicas, caches, logs, support attachments, exports, search indexes, archives, and backups.

Challenge and Submission URL:
https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

---

## 1. Project Overview & Approach

In modern distributed microservice architectures, an automated privacy workflow often reports **Complete** when personal data remains lingering in read replicas, logs, search indexes, or customer service tickets. Furthermore, active asynchronous replication pipelines, data connectors, and backup restores can silently recreate deleted data.

This solution implements a **Deterministic Grounded Core** audit engine that does not rely on unconstrained LLM hallucinations or external API calls, operating with zero external token cost and 100% deterministic reproducibility.

### Key Architectural Pillars

```text
Deletion Request (case_id, email, audit_at, request_text)
                  │
                  ▼
   [1. Request Intent Classifier]
   ├── Non-deletion (GDPR Art. 15, opt-out) ──► NOT_APPLICABLE (steps_json = [])
   └── Authorized deletion
                  │
                  ▼
   [2. Identity Graph Resolver]
   ├── Current identities (user_identities.csv)
   └── Historical changes (user_audit_log.csv: email, phone, name, hash)
                  │
                  ▼
   [3. Evidence Indexer & Temporal Cutoff Engine]
   ├── 94 Multi-modal evidence files (JSON, SQL replicas, logs, txt, PDFs)
   └── Strict cutoff filter: captured_at <= audit_at (zero post-audit leakage)
                  │
                  ▼
   [4. Policy & Residual Risk Analyzer]
   ├── deletion_rules.csv (15 data categories: DELETE, REDACT, ANONYMIZE, RETAIN)
   ├── Prohibited residual copies (databases, search indexes, exports, attachments)
   ├── Exposed PII in tombstones (identity_service) or support conversations
   ├── Active data synchronization flows (integration_service)
   └── Unblocked backup restore risks (backup_service)
                  │
                  ▼
   [5. Canonical Step Serializer]
   ├── Incomplete: FINDINGS (evidence_id) -> REMEDIATION ("") -> VERIFICATION ("")
   ├── Complete: VERIFICATION (evidence_id proving state at audit_at)
   └── Canonical operation & resource sorting (1-indexed consecutive step numbering)
                  │
                  ▼
               output.csv
```

1. **Request Intent Classification (`code/classifier.py`):**
   - Distinguishes genuine deletion requests from non-deletion requests (e.g., GDPR Article 15 access copies, CCPA reporting requests, shipping address rectifications, marketing opt-outs).
   - Multi-lingual keyword and regex intent detection guarantees `NOT_APPLICABLE` with `steps_json=[]` when destructive erasure was not authorized.

2. **Historical Identity Graph Resolution (`code/identity.py`):**
   - Reconstructs user identities across case-insensitive emails, historical email migrations from `user_audit_log.csv`, telephone numbers, SHA-256 email hashes, and full legal names.
   - 100% of the 550 evaluation and sample requests map to stable user identities.

3. **Multi-Format Evidence Ingestion (`code/evidence_loader.py`):**
   - Normalizes evidence across 94 artifacts:
     - `service_resource_export_*.json`: Periodic service status exports across 8 systems.
     - `customer_data_snapshot_bundle_*.json`: Profile records, tombstones, and audit ledgers.
     - `customer_data_inventory_*.sql` & `customer_data_read_replica_*.sql`: SQLite database snapshots used to detect asynchronous replication drift.
     - `resource_lookup_trace_*.log` & `service_events_*.log`: HTTP readbacks (404 vs 200) and service-level checkpoints.
     - `customer_account_handover_*.txt`: Pipe-delimited operational handovers.
     - PDF attachments (`delivery_correction_attachment.pdf`) parsed via `pypdf`.

4. **Strict Temporal Cutoff Enforcement:**
   - Centralized filtering ensures that only evidence captured at or before `audit_at` is evaluated. Post-audit observations never influence audit decisions.

5. **Deletion Policy & Canonical Step Ordering (`code/policy.py`, `code/serializer.py`):**
   - Applies the 15 categories from `deletion_rules.csv`.
   - Adheres strictly to the 3-phase canonical sequence:
     - `FINDING`: `REPORT_REMAINING_RECORD` < `REPORT_EXPOSED_PII` < `REPORT_ACTIVE_DATA_FLOW` < `REPORT_RESTORE_RISK`.
     - `REMEDIATION`: `DISABLE_DATA_FLOW` < `BLOCK_RESTORE` < `DELETE_RECORD` < `REDACT_RECORD` < `ANONYMIZE_RECORD`.
     - `VERIFICATION`: `VERIFY_RECORD_ABSENT` < `VERIFY_RECORD_PRESENT` < `VERIFY_RECORD_REDACTED` < `VERIFY_RECORD_ANONYMIZED` < `VERIFY_DATA_FLOW_DISABLED` < `VERIFY_RESTORE_BLOCKED`.
   - Secondary sorting: `system_id` ascending, then `resource_id` ascending.

---

## 2. Repository Layout

```text
├── AGENTS.md                              # Authoritative coding agent operating contract
├── problem_statement.md                   # Full challenge specification
├── README.md                              # This document: setup & approach overview
├── log.txt                                # Root append-only session and turn log
├── output.csv                             # Final generated output (518 evaluation rows)
├── pytest.ini                             # Pytest configuration
├── .gitignore                             # Git exclusion rules
├── code/
│   ├── __init__.py                        # Code package initializer
│   ├── classifier.py                      # Request intent classification module
│   ├── engine.py                          # Core audit decision engine
│   ├── evidence_loader.py                 # Multi-format evidence parser and indexer
│   ├── identity.py                        # Identity graph resolver
│   ├── main.py                            # Main CLI pipeline entry point
│   ├── policy.py                          # Deletion rules, operations, and state enums
│   ├── serializer.py                      # Canonical step sorting & CSV serialization
│   └── evaluation/
│       ├── __init__.py                    # Evaluation package initializer
│       ├── main.py                        # Evaluation harness
│       ├── evaluation_report.md           # Benchmark accuracy & synthetic cases report
│       └── usage_report.md                # Model calls, token counts, and cost breakdown
├── dataset/
│   ├── deletion_requests.csv              # 518 evaluation requests
│   ├── sample_deletion_requests.csv       # 32 sample requests
│   ├── sample_output.csv                  # Reference answers for 32 samples
│   ├── user_identities.csv                # Current user identity snapshots
│   ├── user_audit_log.csv                 # Historical identity changes
│   ├── system_activity.csv                # Global event stream
│   ├── deletion_rules.csv                 # Data category policy matrix
│   ├── evidence_files.csv                 # Manifest of supplied evidence files
│   └── evidence/                          # 94 evidence files (JSON, SQL, logs, txt, PDFs)
└── tests/
    └── test_audit_engine.py               # Unit, integration, and invariant tests
```

---

## 3. Setup and Installation

### Prerequisites
- Python 3.10, 3.11, or 3.12 (tested on Python 3.12.6 AMD64)
- Git

### Environment Setup
Create a virtual environment and install the required dependencies:

```bash
# Clone the repository
git clone https://github.com/studioussagar/hackerrank-orchestrate-october26.git
cd hackerrank-orchestrate-october26

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install required dependencies
pip install pandas pytest pypdf
```

---

## 4. Running the Solution

### 1. Execute Full Audit Pipeline (Generates `output.csv`)
To process all 518 evaluation requests from `dataset/deletion_requests.csv` and write the canonical `output.csv` to the repository root:

```bash
python code/main.py
```

*Execution performance:* Completes in ~0.8 to 1.2 seconds (~500+ requests/sec).

### 2. Run Public Sample Benchmark
To run against `dataset/sample_deletion_requests.csv` and inspect output:

```bash
python code/main.py --sample
```

### 3. Run Automated Tests
Execute the automated test suite verifying identity resolution, multi-lingual classification, temporal cutoffs, canonical sorting, and invariant rules:

```bash
pytest tests/
```

### 4. Run Evaluation Harness & Generate Reports
To evaluate predictions against ground truth and regenerate the Markdown reports under `code/evaluation/`:

```bash
python code/evaluation/main.py
```

### 5. Validate Output CSV Invariants
To verify that `output.csv` strictly conforms to the challenge contract (518 rows, exact columns, sorted order, valid 7-key JSON steps):

```bash
python -c "from code.serializer import save_output_csv; import pandas as pd; df = pd.read_csv('output.csv'); assert len(df) == 518; assert list(df.columns) == ['case_id', 'deletion_status', 'steps_json']; print('output.csv is 100% valid!')"
```

---

## 5. Evaluation and Resource Usage

- **Evaluation Report:** [`code/evaluation/evaluation_report.md`](./code/evaluation/evaluation_report.md)
  - Documents case-level deletion-status accuracy, field-level accuracy, and sequence accuracy.
  - Contains full confusion matrix.
  - Documents 3 custom synthetic evaluation test cases (`case_syn_01` replication drift, `case_syn_02` tombstone hygiene & statutory retention, `case_syn_03` GDPR Art. 15 French access request).
  - Documents failures discovered and engineering improvements implemented.
- **Usage Report:** [`code/evaluation/usage_report.md`](./code/evaluation/usage_report.md)
  - Full-dataset run token & cost metrics: 0 external API calls, 0 tokens, **$0.00** external runtime cost.

---

## 6. Packaging & Submission Checklist

The HackerRank submission requires four items:

| Item | File | Description |
|---|---|---|
| **Code Submission** | `code.zip` | Solution code, `README.md`, and `code/evaluation/` reports |
| **Output Submission** | `output.csv` | Exactly 518 answer rows for `dataset/deletion_requests.csv` |
| **Chat Transcript** | `log.txt` | Complete agent turn log following `AGENTS.md` §5 |
| **AI Interview** | Live Session | Explanation of architecture, evidence models, and evaluation |

### Packaging `code.zip`

To package `code.zip` without bundling `dataset/`, virtual environments, or build caches:

**Windows (PowerShell):**
```powershell
# Remove any cached bytecode
Get-ChildItem -Path code -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Compress into code.zip
Compress-Archive -Path README.md, code -DestinationPath code.zip -Force
```

**macOS / Linux:**
```bash
zip -r code.zip README.md code -x "*/__pycache__/*" "*/.venv/*" "*/venv/*" "*/node_modules/*" "*/.git/*" "*/.DS_Store"
```

Confirm that `code.zip` contains:
- `README.md`
- `code/main.py`
- `code/classifier.py`
- `code/engine.py`
- `code/evidence_loader.py`
- `code/identity.py`
- `code/policy.py`
- `code/serializer.py`
- `code/evaluation/evaluation_report.md`
- `code/evaluation/usage_report.md`
- `code/evaluation/main.py`

Upload `code.zip`, `output.csv`, and `log.txt` to:
https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
