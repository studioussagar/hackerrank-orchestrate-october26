# Evaluation and Testing Plan

## 1. Evaluation goals
Measure both final status correctness and the quality of the emitted steps. The challenge scoring considers deletion status, identity resolution, remaining data/recreation risk discovery, policy application, evidence references, and remediation/verification completeness and order.

## 2. Test layers
### Unit tests
- Request intent: deletion vs access/correction/export/marketing opt-out.
- Current identity match.
- Historical identifier recovery.
- Ambiguous identity collision.
- Timestamp cutoff: event before, exactly at, and after `audit_at`.
- Policy treatment: delete, redact, anonymize, retain, tombstone.
- Active data flow and restore-risk detection.
- Evidence reference validation.
- Operation/state/phase validation.
- Deterministic sort and step numbering.
- JSON-in-CSV serialization.

### Integration tests
- Ingest all participant-facing CSVs.
- Parse each supported evidence format that actually exists.
- Process a small set of sample requests end-to-end.
- Run all requests and ensure no case is silently skipped.
- Validate output against the exact contract.

### Regression tests
- Store test fixtures made from participant-facing evidence and synthetic cases.
- Re-run after each rule/parser/identity change.
- Never store hidden labels or use organizer-only files.

## 3. Public sample evaluation
Use the 32 public requests and `sample_output.csv` as a smoke test and reference. Compare normalized JSON objects while preserving step array order. Do not hardcode sample case IDs or use sample mappings as an answer lookup.

## 4. Required metrics
Write metrics to `code/evaluation/evaluation_report.md`.

### Case-level status accuracy
On public sample cases:
`correct status count / number of evaluated sample cases`.

### Step-level accuracy
Compare predicted and reference step tuples:
`(phase, system_id, resource_id, operation, state, evidence_id)`.

### Field-level accuracy
Measure each required field independently and report the denominator. Explain normalization rules.

### Sequence accuracy
Percentage of cases whose ordered step sequence matches the reference sequence exactly.

### Additional metrics recommended
- Evidence citation validity rate.
- Temporal-leakage violations (target: 0).
- Invalid operation/state rate (target: 0).
- Output contract pass rate (target: 100%).
- Required-row coverage (target: 100%).
- Retention-rule violation rate (target: 0).
- Unsupported COMPLETE rate (target: 0 in custom tests).

Do not claim accuracy on the hidden 518-case set unless a legitimate visible reference is available. Report only metrics actually computed.

## 5. Minimum three custom cases
Create at least three participant-generated tests with synthetic data:
1. **Historical email:** request email appears only in identity history, while the current email differs; an old identifier is still present in a secondary record.
2. **Recreation path:** primary record is deleted but an active import or sync can re-create it.
3. **Retained tombstone:** policy requires a stable `user_id` tombstone while direct identifiers are redacted and a compliance record remains.
Recommended extras:
4. Non-deletion request (access/export/correction) must be NOT_APPLICABLE.
5. Post-cutoff evidence must not alter the earlier answer.
6. Required retained record is absent, which should be detected as a policy violation.
7. Evidence file exists in manifest but content does not match target user; do not associate it.
8. Two users share a weak identifier; resolver must avoid an unsupported merge.

## 6. Evaluation process
1. Run static checks and unit tests.
2. Run public sample evaluation.
3. Review every mismatch by category: intent, identity, evidence parsing, temporal state, policy, graph, ordering, serialization.
4. Fix root causes, not individual case IDs.
5. Re-run all tests.
6. Run the full dataset once after code freeze.
7. Capture real model call/token/cost instrumentation for usage report.
8. Save final command, environment/version info, and output hash in the run log (avoid sensitive data).

## 7. Usage report requirements
Instrument model calls if models are used:
- provider and exact model name;
- number of calls;
- input/output token counts from provider usage metadata;
- total tokens and average per request;
- estimated price and source/rate date;
- per-model and aggregate totals.

If no model is used, state that explicitly and report zero model calls/tokens and no model inference cost. Do not guess token counts or prices. If provider usage metadata is unavailable, mark it unavailable and explain the estimation method.

## 8. Quality gates before packaging
- Exactly 518 data rows plus header.
- Exact header and column order.
- Sorted `case_id`, no duplicates, no missing requests.
- Every `steps_json` cell parses.
- Exactly seven keys per step.
- Allowed enums only.
- Consecutive step numbering.
- Correct phase and operation order.
- Valid evidence references where required.
- Empty evidence ID on proposed remediation/future verification for INCOMPLETE cases.
- `NOT_APPLICABLE` has `[]`.
- No use of post-cutoff evidence.
- No dataset or secrets in ZIP.
