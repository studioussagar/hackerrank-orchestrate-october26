# AI Judge Interview Preparation

## 1. Thirty-second summary
"I built an evidence-driven deletion audit pipeline. It classifies whether deletion was requested, resolves current and historical identifiers, indexes participant-visible evidence, reconstructs resource state at `audit_at`, applies policy rules, checks active data-flow and restore paths, and emits deterministic, schema-validated steps. The LLM, if used, assists with bounded extraction or intent interpretation; deterministic code owns the final policy decision and output contract."

## 2. Likely questions and answer points

### Why not trust the reported deletion status?
It is a workflow claim. A primary deletion can succeed while replicas, exports, indexes, attachments, logs, or backups retain data, and active sync/restore processes can recreate it. The agent verifies resource state from evidence at the cutoff.

### How do you resolve historical identifiers?
Start from the request email, connect it to current identity and audit history, then expand through supported stable IDs and evidence links. Every link has provenance; weak or ambiguous matches are not merged automatically.

### How do you avoid temporal leakage?
Each case has an `audit_at` cutoff. Relevant events/observations after that cutoff are excluded from the decision. Tests include post-cutoff evidence.

### How do you decide COMPLETE?
Only if all relevant copies have their policy-required treatment, required retained records remain, tombstones contain only permitted identifiers, and no active recreation or restore path can reintroduce prohibited data. COMPLETE output contains evidence-backed verification steps only.

### What happens to a tombstone?
Apply the exact policy. A stable `user_id` may remain when permitted, but prohibited direct identifiers such as name, email, phone, and email hash must be removed if the relevant rule requires redaction. The record itself is not automatically deleted.

### How do you order remediation?
Findings first, then remediation, then verification. Disable active flows and block unsafe restores before changing dependent records. Respect downstream/source dependencies and the required canonical sorting order.

### What does the LLM do?
It may classify multilingual request intent or extract structured facts from unstructured evidence. It does not invent evidence or decide final compliance. Outputs are schema-validated and checked against source timestamps and evidence IDs.

### How do you evaluate?
Use public sample cases, unit tests, integration/contract tests, and at least three synthetic edge cases. Report case status, step/field, and sequence metrics, plus evidence citation validity, temporal leakage, and output contract pass rate. Do not claim hidden-set accuracy without reference labels.

### How do you control cost?
Cache parsing and model extraction, send minimal evidence excerpts, use deterministic matching for structured data, batch safe independent extraction, and instrument provider-reported token usage and actual calls.

### What are the main limitations?
Evidence quality and parser coverage constrain conclusions. OCR can fail; timestamps may conflict; identifiers may be ambiguous. The system records these limits and avoids unsupported COMPLETE decisions.

## 3. Be ready to demonstrate
- One NOT_APPLICABLE request.
- One COMPLETE request with evidence-backed verification.
- One INCOMPLETE request with a remaining record and/or recreation path.
- A historical email match.
- A tombstone/retention case.
- A post-cutoff event excluded from the decision.
- A malformed output caught by the validator.

## 4. Interview integrity
Describe what the implementation actually does. Do not claim model use, evaluation scores, cost savings, or test results that were not measured. Be able to point to the relevant code and reports.
