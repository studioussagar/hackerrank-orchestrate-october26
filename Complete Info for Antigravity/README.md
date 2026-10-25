# Ghost Data Still Exists — Documentation Pack

This pack specifies a solution for the HackerRank Orchestrate October 2026 challenge, **Ghost Data Still Exists**.

## Documents
1. `01_product_requirements.md` — Product requirements, scope, personas, requirements, acceptance criteria.
2. `02_system_architecture.md` — Architecture, component responsibilities, technology recommendations.
3. `03_workflow_and_state_machine.md` — End-to-end workflow, decision logic, temporal rules, remediation ordering.
4. `04_data_and_evidence_model.md` — Inputs, normalized evidence model, identity resolution, evidence provenance.
5. `05_evaluation_and_testing.md` — Evaluation design, metrics, test cases, quality gates.
6. `06_implementation_plan.md` — Phased implementation plan and repository layout.
7. `07_optional_web_dashboard_design.md` — Optional UI/UX specification. A website is not required by the challenge.
8. `08_llm_prompts_and_guardrails.md` — Structured AI usage, output validation, safety and privacy controls.
9. `09_runbook_and_submission_checklist.md` — Setup, execution, packaging, submission checks.
10. `10_ai_judge_interview_prep.md` — Interview topics and model answers.
11. `11_antigravity_build_instructions.md` — Instructions for using Google Antigravity as the coding agent.

## Ground truth for the implementation
The uploaded `AGENTS.md` and `problem_statement.md` take precedence over this planning pack. In particular:
- Required output columns: `case_id,deletion_status,steps_json`.
- Exactly 518 prediction rows, sorted by `case_id`.
- Allowed statuses, phases, operations, and states are strictly constrained.
- Findings and COMPLETE verification steps cite participant-visible evidence IDs.
- Proposed remediation and future verification steps for INCOMPLETE cases use `evidence_id: ""`.
- `NOT_APPLICABLE` uses `steps_json: []`.
- Decisions must reflect state at each request's `audit_at`, not later evidence.
- Do not use organizer-only files or hardcode case labels.
- Required reports: `code/evaluation/evaluation_report.md` and `code/evaluation/usage_report.md`.
- `log.txt` must be append-only and follow the exact logging contract in `AGENTS.md`.

## Website decision
A website is optional and not required for the scored deliverable. Build the CLI/evaluation pipeline first. Only add the optional dashboard if the core output is correct and time remains.
