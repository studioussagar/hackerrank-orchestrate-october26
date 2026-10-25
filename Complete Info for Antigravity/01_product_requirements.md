# Product Requirements Document (PRD)
## Ghost Data Still Exists — AI-Powered Deletion Audit Agent

**Document status:** Implementation-ready baseline; validate against the repository's current files before coding.  
**Primary objective:** Produce evidence-backed deletion audit decisions and ordered actions for every request in `dataset/deletion_requests.csv`.

## 1. Problem statement
A deletion workflow can report success while personal data persists in secondary databases, replicas, logs, support attachments, search indexes, analytics exports, archives, or backups. Synchronization, import, and restore jobs may recreate data after a primary record is deleted. The system must determine whether an authorized deletion is actually complete at the request's `audit_at` cutoff, not merely trust workflow status fields.

## 2. Product goal
For every deletion request, generate exactly one row in root-level `output.csv` with:
- `case_id`
- `deletion_status`
- `steps_json`

The agent must identify relevant current and historical identifiers, inspect supplied evidence, apply `deletion_rules.csv`, identify remaining violations and recreation risks, and generate the required evidence-backed verification or ordered remediation steps.

## 3. Users and stakeholders
- **Challenge evaluator:** Requires exact schema, deterministic ordering, valid operations/states, and correct evidence references.
- **Privacy/compliance analyst:** Needs traceable findings, policy-consistent treatment, and preservation of required records.
- **Engineering/operator:** Needs actionable, dependency-aware remediation steps.
- **AI Judge/interviewer:** Needs a clear explanation of architecture, evidence handling, evaluation, model usage, and trade-offs.

## 4. Scope
### In scope
- Parse all participant-facing CSV inputs and local evidence files.
- Determine whether `request_text` authorizes deletion.
- Resolve current and historical identifiers from identity snapshots and audit history.
- Search global activity and evidence for related records, resources, events, and processes.
- Respect `audit_at`; ignore evidence created after the cutoff for the case decision.
- Apply category- and condition-specific deletion rules.
- Handle tombstones and retained records correctly.
- Identify active data flows and restore risks.
- Produce ordered findings, remediation, and verification steps using only allowed values.
- Generate evaluation and usage reports.
- Provide a reproducible terminal command and submission package.

### Out of scope
- Executing destructive operations against real production systems. This challenge agent proposes remediation and verification; it does not actually delete production data.
- Treating an LLM response as authoritative evidence.
- Building a production privacy-request management platform.
- A web interface as a core deliverable; it is optional and must not delay the CLI solution.

## 5. Definitions
- **Deletion request:** A request whose text actually authorizes deletion, not merely access, correction, export, or marketing opt-out.
- **Current identifier:** Identifier in the latest identity snapshot available in the supplied data.
- **Historical identifier:** Prior identifier evidenced in `user_audit_log.csv` or other grounded records.
- **Finding:** A supported policy violation or active recreation risk.
- **Remediation step:** A proposed action required to achieve policy-compliant state.
- **Verification step:** A check that must pass to establish the final state.
- **Tombstone:** A record that may retain a stable `user_id` reference while direct identifiers must be removed.
- **Audit cutoff:** `audit_at`, the latest timestamp whose evidence can influence a case decision.

## 6. Functional requirements
### FR-01 — Input ingestion
Read the files under `dataset/`, including:
`deletion_requests.csv`, `sample_deletion_requests.csv`, `sample_output.csv`, `user_identities.csv`, `user_audit_log.csv`, `system_activity.csv`, `deletion_rules.csv`, `evidence_files.csv`, and files beneath `dataset/evidence/`.

Handle missing, malformed, empty, and unexpected records without silently dropping them. Report ingestion errors to stderr or a run report.

### FR-02 — Authorization classification
Classify each request as deletion-authorizing or non-deletion. Requests for access, correction, export, marketing opt-out, or another non-deletion action must yield `NOT_APPLICABLE`, even if other columns resemble a deletion case. `NOT_APPLICABLE` must have `steps_json=[]`.

### FR-03 — Identity resolution
Resolve the supplied email against current and historical identifiers. Expand to related identifiers only through supported links. Preserve provenance for every link. Avoid merging people based solely on weak or non-unique attributes.

### FR-04 — Evidence discovery
Use `evidence_files.csv` as a file manifest, not as proof of case membership. Inspect file contents and connect evidence through identifiers, hashes, resource IDs, system IDs, timestamps, and other grounded links. Support text, JSON, logs, SQL exports, PDFs, and images using suitable parsers/OCR where needed.

### FR-05 — Temporal reconstruction
Determine resource and process state at `audit_at`. Evidence created after the cutoff must not change the answer. Reconstruct relevant events in timestamp order, distinguishing reported claims from confirmed resource state.

### FR-06 — Policy application
Apply `deletion_rules.csv` to each relevant record and category. The engine must distinguish whole-record deletion, identifier redaction, anonymization, required retention, and tombstone preservation. Do not remove required retained records.

### FR-07 — Recreation-risk analysis
Identify active sync/import/export/indexing/restore processes that can reintroduce prohibited data. A deletion cannot be COMPLETE if a relevant active recreation path remains unresolved.

### FR-08 — Status decision
Allowed values are exactly:
- `COMPLETE`
- `INCOMPLETE`
- `NOT_APPLICABLE`

A COMPLETE decision requires evidence that all relevant copies received required treatment, retained records remain available and compliant, and recreation paths are resolved.

### FR-09 — Step generation
Each step contains exactly:
`step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`.

Use only allowed phases, operations, and states from `problem_statement.md`. Step numbers begin at 1 and are consecutive. Phase order is FINDING, REMEDIATION, VERIFICATION. Within each phase, use the exact operation ordering specified by the source contract, then sort by `system_id` and `resource_id`.

For COMPLETE, emit only evidence-backed verification steps. For INCOMPLETE, emit findings, the complete ordered remediation plan, and post-remediation verification steps. Proposed remediation and future verification have an empty `evidence_id`. For NOT_APPLICABLE, emit an empty array.

### FR-10 — Output contract
Write root-level `output.csv` with exact columns in this order:
`case_id,deletion_status,steps_json`
Produce one row per input case (the source contract specifies 518 cases), sorted by `case_id`. Serialize `steps_json` as a valid JSON array and CSV-escape it correctly.

### FR-11 — Evaluation reporting
Include `code/evaluation/evaluation_report.md` with case-level status accuracy, step-level and field-level accuracy, sequence accuracy, at least three participant-created evaluation cases, failures found, and improvements made.

### FR-12 — Model usage reporting
Include `code/evaluation/usage_report.md` summarizing the final full-dataset run: providers and model names, model calls, input/output tokens, total and average tokens per request, estimated total and per-request cost, and per-model/overall totals when multiple models are used. Never invent usage or cost data; instrument actual calls and clearly state estimates/unknowns.

### FR-13 — Trace logging
Follow `AGENTS.md`: append session-start and per-turn entries to root `log.txt`; do not rewrite old entries; do not log secrets or sensitive personal data. Keep exact harness and runtime model identifiers accurate. Export and submit the relevant agent trace if required by the current submission instructions.

## 7. Non-functional requirements
- **Correctness:** Decisions are grounded in evidence and policy.
- **Determinism:** Stable sorting, serialization, and rule application.
- **Auditability:** Every finding and COMPLETE verification has a participant-visible evidence reference.
- **Temporal integrity:** No post-`audit_at` evidence leakage.
- **Privacy:** Minimize exposure of identifiers in logs and reports; never package secrets.
- **Robustness:** Graceful handling of malformed files and partial extraction.
- **Efficiency:** Cache file parsing and identifier searches; avoid unnecessary LLM calls.
- **Portability:** Run from repository root on supported environments with documented setup.
- **Maintainability:** Separate ingestion, identity, evidence, policy, decision, output, and evaluation logic.

## 8. Acceptance criteria
1. The run completes from a clean environment using documented commands.
2. Root `output.csv` contains the exact header and one row per request, sorted by `case_id`.
3. Every `steps_json` cell parses as a JSON array.
4. Each step has exactly the seven required keys and allowed values.
5. Step numbers are consecutive and phases/operations are ordered as specified.
6. NOT_APPLICABLE rows have `[]`.
7. COMPLETE cases contain only evidence-backed verification steps.
8. INCOMPLETE findings cite participant-visible evidence; proposed remediation and future verification use `evidence_id: ""`.
9. No case decision uses evidence after `audit_at`.
10. Retention and tombstone rules are respected.
11. No organizer-only truth, hardcoded labels, or case-family shortcuts are used.
12. The evaluation and usage reports are included and accurately describe the final run.
13. `code.zip` excludes the dataset, virtual environments, caches, nested archives, secrets, and credentials.
14. `log.txt` follows the required append-only format.

## 9. Assumptions and open questions
- The repository's current `problem_statement.md` and `AGENTS.md` are authoritative if any details here conflict.
- Exact category/condition rules must be read from `deletion_rules.csv`; do not assume generic policy semantics.
- Evidence parsers should be selected based on actual file formats present.
- LLM usage is optional; deterministic methods may be used where adequate.
- No website is required for the scored solution.
