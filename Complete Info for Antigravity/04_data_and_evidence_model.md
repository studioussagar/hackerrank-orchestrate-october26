# Data and Evidence Model

## 1. Source files and meaning
| Source | Purpose | Trust/handling note |
|---|---|---|
| `deletion_requests.csv` | Cases requiring predictions | `audit_at` is the decision cutoff; reported status is not proof |
| `sample_deletion_requests.csv` | Public sample requests | Useful for smoke tests |
| `sample_output.csv` | Public sample outputs | Reference for serialization and expected behavior on samples |
| `user_identities.csv` | Current identity snapshot | Current identity only; not sufficient for historical lookup |
| `user_audit_log.csv` | Historical identity changes | Use to recover old identifiers and their effective timeline |
| `system_activity.csv` | Global operational events | May include unrelated users and claims of success |
| `deletion_rules.csv` | Policy for data categories/conditions | Authoritative treatment rules |
| `evidence_files.csv` | Evidence manifest | Maps file IDs to paths/origin/capture time; does not establish case relevance |
| `dataset/evidence/**` | Business evidence | Must inspect contents and connect via grounded identifiers/resources |

## 2. Suggested normalized entities
Keep a normalized internal representation; do not change the required output schema.

### Request
- `case_id`
- `email`
- `requested_at`
- `reported_status`
- `reported_at`
- `audit_at`
- `request_text`
- `deletion_authorized` (derived)
- `subject_user_id` (derived, if resolvable)

### Identifier
- `identifier_type` (email, phone, email_hash, user_id, customer_id, account_id, etc.)
- `identifier_value` (protect in logs)
- `valid_from`, `valid_to` if available
- `source_type`, `source_id`
- `confidence/reason` (internal diagnostic, not a replacement for evidence)

### Evidence item
- `evidence_id`
- `evidence_kind` (file, activity, audit)
- `system_id`
- `resource_id`
- `category`
- `observed_state`
- `observed_identifiers`
- `event_time`, `capture_time`
- `source_origin`
- `extraction_method`
- `extraction_success`
- `content_hash` (optional for integrity/deduplication)
- `links_to_subject` and `link_reason`

### Policy rule
- Rule key/category/condition exactly as supplied.
- Required treatment.
- Permitted identifiers or fields.
- Retention requirements.
- Effective conditions if represented in the CSV.

Do not invent policy columns or semantics before inspecting the real file.

### Data-flow edge
- `source_system/resource`
- `destination_system/resource`
- `process_id`
- `flow_type` (sync, import, export, indexing, restore, etc.)
- `state_at_cutoff`
- `evidence_id`
- `can_recreate_prohibited_data`

### Step
- `step_no`
- `phase`
- `system_id`
- `resource_id`
- `operation`
- `state`
- `evidence_id`

The Step schema must exactly match the source contract.

## 3. Evidence provenance
Every extracted fact should retain:
- the original file/activity/audit ID;
- path or record locator;
- source timestamp and capture timestamp;
- the identifier/resource match that connected it to the case;
- parser/OCR method and success status;
- whether it was eligible at the case cutoff.

Never cite an evidence manifest row as if it proves the content of the underlying file. Inspect the file first.

## 4. Temporal model
For each case, define `cutoff = audit_at`. Evidence can support the decision only if its relevant event/observation time is at or before cutoff. Carefully distinguish event time from capture time when the file format provides both. If timestamps are missing or contradictory, preserve uncertainty and avoid unsupported claims.

## 5. Identity graph
Represent identifiers and records as nodes, with typed edges:
- `same_subject_as`
- `historically_used_by`
- `contained_in`
- `copied_to`
- `restored_to`
- `indexed_from`
- `retained_under_policy`

Each edge should carry source evidence and time validity. Do not create edges from name/email similarity alone if collisions or ambiguity are possible.

## 6. Policy-to-treatment mapping
Translate each row of `deletion_rules.csv` into a data-driven rule. At runtime, for each relevant resource:
1. Determine the applicable category and condition.
2. Find required treatment.
3. Compare observed state and identifiers with required state.
4. Emit a finding only when supported by evidence.
5. Add remediation if the resource is non-compliant.
6. Add verification for the required final state.
7. Ensure required retained records remain available.

## 7. Data minimization
- Avoid writing raw emails, phone numbers, or names to debug logs.
- Avoid placing full evidence contents into model prompts when a minimal excerpt or extracted fields suffice.
- Keep local evidence and dataset out of the submission ZIP.
- Redact secrets and sensitive data from agent traces before upload.
