# Implementation Plan

## Phase 0 — Repository and contract reconnaissance
**Goal:** Know the real dataset and contract before designing parsers.
- Read `AGENTS.md`, `problem_statement.md`, `README.md`, and `agent_trace_instructions.md`.
- Start the required append-only `log.txt` correctly in the coding harness.
- Inspect directory tree and every CSV header/sample.
- Inventory evidence file extensions and sizes.
- Inspect public sample outputs and policy rows.
- Confirm Python version and available dependencies.
**Exit criteria:** Input inventory, output contract, parser plan, no hidden/organizer data used.

## Phase 1 — Deterministic ingestion and output skeleton
- Implement path resolution relative to repository root.
- Parse CSVs with correct encoding/newline handling.
- Parse timestamps and retain raw values.
- Add output writer using `csv.DictWriter` and `json.dumps`.
- Add contract validator.
**Exit criteria:** All 518 case IDs appear once in sorted output; JSON arrays parse; no hardcoded labels.

## Phase 2 — Authorization and identity
- Implement deletion-intent rules.
- Resolve current identity and historical aliases.
- Add collision handling and provenance.
- Add tests for multilingual and non-deletion requests.
**Exit criteria:** NOT_APPLICABLE behavior correct; historical identifier tests pass.

## Phase 3 — Evidence extraction and indexing
- Build manifest-driven parsers for actual formats present.
- Parse text, JSON, logs, SQL snapshots, PDFs, and images as needed.
- Preserve evidence IDs and source timestamps.
- Index identifiers/resource IDs/system IDs.
**Exit criteria:** Every evidence file is either processed or has a recorded parse failure; manifest alone is not used as proof.

## Phase 4 — Temporal state and policy
- Build cutoff-aware state reconstruction.
- Apply `deletion_rules.csv` dynamically.
- Handle required retention and tombstones.
- Separate operation claims from observed states.
**Exit criteria:** Unit tests cover pre-/post-cutoff events and each policy treatment.

## Phase 5 — Data-flow and restore graph
- Extract process edges from activity and evidence.
- Determine whether relevant paths are active at cutoff.
- Trace data-bearing sources to destination copies.
**Exit criteria:** Active recreation paths block COMPLETE and generate supported findings.

## Phase 6 — Remediation planner and verification
- Generate allowed operations only.
- Respect dependency ordering.
- Include verification for every target/process.
- Sort canonically and number after sorting.
**Exit criteria:** Output passes operation/state/order validator.

## Phase 7 — Optional LLM/VLM
Only add after deterministic core is tested.
- Use LLM for ambiguous multilingual intent or unstructured evidence extraction if needed.
- Use VLM/OCR only for images whose contents are relevant.
- Require structured JSON, evidence references, and schema validation.
- Cache calls and minimize PII.
**Exit criteria:** Demonstrated improvement over baseline without invalid outputs or unsupported claims.

## Phase 8 — Evaluation and hardening
- Run unit, integration, sample, and custom tests.
- Diagnose errors by root-cause category.
- Add `evaluation/evaluation_report.md` and `evaluation/usage_report.md`.
- Run full dataset and inspect output.
**Exit criteria:** All contract checks pass; metrics reflect actual results.

## Phase 9 — Packaging and interview readiness
- Package code only; exclude `dataset/`, caches, virtual environments, nested archives, secrets.
- Ensure README contains clean setup/run instructions.
- Include evaluation reports.
- Submit root `output.csv`, `code.zip`, `log.txt`, and trace ZIP if requested by the current event.
- Prepare explanation of identity, evidence, time, policy, remediation, and evaluation.
