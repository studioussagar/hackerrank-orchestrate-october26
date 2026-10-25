# Workflow and State Machine

## 1. Per-case workflow

```mermaid
flowchart TD
    A[Read request] --> B{Does request_text authorize deletion?}
    B -- No --> N[NOT_APPLICABLE; steps_json = []]
    B -- Yes --> C[Resolve current + historical identifiers]
    C --> D[Set cutoff = audit_at]
    D --> E[Search participant-visible records and evidence]
    E --> F[Reconstruct resource/process state at cutoff]
    F --> G[Apply deletion_rules.csv]
    G --> H[Find remaining records, exposed identifiers, active flows, restore risks]
    H --> I{Any policy violation or unresolved recreation risk?}
    I -- Yes --> J[INCOMPLETE]
    J --> K[Generate findings]
    K --> L[Plan remediation in dependency order]
    L --> M[Generate future verification checks]
    I -- No --> P[COMPLETE]
    P --> Q[Generate evidence-backed verification steps only]
    N --> Z[Validate and serialize]
    M --> Z
    Q --> Z
```

## 2. Request authorization
Intent must be classified from `request_text`. Non-deletion requests such as access, correction, export, or marketing opt-out are NOT_APPLICABLE even if the workflow metadata looks like a deletion case. Multilingual requests may require multilingual keyword/rule coverage or a bounded model classifier. Any model classification should produce a structured result and be validated; ambiguous cases should not be treated as authorized deletion without evidence.

## 3. Identity resolution procedure
1. Normalize email and other identifiers conservatively (e.g., trim whitespace and case-fold email where appropriate).
2. Find direct matches in current identity snapshot.
3. Search historical identity audit entries, including old emails/phones/hashes.
4. Link records through stable `user_id` and grounded resource references.
5. Expand the identifier set iteratively across evidence.
6. Track source, timestamp, and reason for each alias.
7. Avoid weak joins and collisions; keep ambiguous candidates separate until corroborated.

## 4. Evidence and temporal procedure
For every candidate evidence item:
- Determine its source timestamp/capture time and its semantic role.
- Exclude it from the case decision if created after `audit_at`.
- Check whether it actually links to the target via an identifier, resource, activity, or other supported relation.
- Classify it as a claim, snapshot, event, process configuration, or verification result.
- Use the strongest available evidence to establish resource state, without treating an event's reported success as proof by itself.

A post-cutoff item may be logged for debugging only if it cannot affect the case result.

## 5. Completeness predicates
A request can be COMPLETE only if all are true:
1. Every relevant copy has the treatment required by the applicable rule.
2. No prohibited direct identifier remains in a retained record or tombstone.
3. Required retained records still exist.
4. No active sync/import/restore path can recreate prohibited data.
5. Current state is supported by evidence at or before `audit_at`.
6. Every emitted COMPLETE verification step cites a participant-visible evidence ID proving the relevant compliant state.

If any violation or active recreation risk is evidenced, status is INCOMPLETE. If required state cannot be established, do not claim COMPLETE; represent the supported violation/risk and verification needs using the contract's allowed operations. Do not invent unsupported findings.

## 6. Remediation ordering
- Phase order: FINDING, then REMEDIATION, then VERIFICATION.
- Within a phase, use the operation order from `problem_statement.md`, followed by `system_id` and `resource_id` ascending.
- Before modifying dependent records, disable active data flows and block unsafe restores.
- Process downstream copies before source records when required by the dependency graph.
- For retained records, redact or anonymize only the fields/category the policy requires; preserve the record.
- Tombstones may preserve stable `user_id` but must remove direct identifiers as specified by policy.
- For each remediation target, include a corresponding post-remediation verification operation.

## 7. Allowed operations and states
### FINDING
- `REPORT_REMAINING_RECORD` / `PRESENT`
- `REPORT_EXPOSED_PII` / `PRESENT`
- `REPORT_ACTIVE_DATA_FLOW` / `ACTIVE`
- `REPORT_RESTORE_RISK` / `ACTIVE`

### REMEDIATION
- `DISABLE_DATA_FLOW` / `DISABLED`
- `BLOCK_RESTORE` / `BLOCKED`
- `DELETE_RECORD` / `ABSENT`
- `REDACT_RECORD` / `REDACTED`
- `ANONYMIZE_RECORD` / `ANONYMIZED`

### VERIFICATION
- `VERIFY_RECORD_ABSENT` / `ABSENT`
- `VERIFY_RECORD_PRESENT` / `PRESENT`
- `VERIFY_RECORD_REDACTED` / `REDACTED`
- `VERIFY_RECORD_ANONYMIZED` / `ANONYMIZED`
- `VERIFY_DATA_FLOW_DISABLED` / `DISABLED`
- `VERIFY_RESTORE_BLOCKED` / `BLOCKED`

Never invent phases, operations, or states.

## 8. Output-specific behavior
- `NOT_APPLICABLE`: `steps_json` is `[]`.
- `COMPLETE`: only verification steps, each with a valid evidence reference.
- `INCOMPLETE`: supported findings + full ordered proposed remediation + future verification steps.
- For findings, cite participant-visible `file_id`, `activity_id`, or `audit_id`.
- For proposed remediation and future verification in INCOMPLETE cases, set `evidence_id` to the empty string.
- Step numbers are consecutive after sorting.
- JSON array order is significant.
