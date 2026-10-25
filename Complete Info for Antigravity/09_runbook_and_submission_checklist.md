# Runbook and Submission Checklist

## 1. Start-up
1. Clone the challenge repository and open a terminal at the repository root.
2. Read `AGENTS.md`, `problem_statement.md`, `README.md`, and `agent_trace_instructions.md`.
3. Use the coding agent from the repository root so the repository logging contract is followed.
4. Create/use the required append-only root `log.txt`.
5. Inspect only participant-facing data under `dataset/` for predictions.

## 2. Build and run
The starter README suggests `python3 code/main.py`. Confirm the repository's actual entry point and environment before use.

Typical sequence:
```bash
python3 -m venv .venv
# Activate the environment for your shell.
pip install -r requirements.txt   # only if this file exists and is maintained
python3 code/main.py
```
Do not create a requirements file containing unused packages. Pin dependencies only when needed and tested.

## 3. Output checks
Run a validator that confirms:
- Exact header `case_id,deletion_status,steps_json`.
- Exactly one data row per request (518 per current contract).
- Rows sorted by `case_id`.
- No missing/duplicate case IDs.
- Status is one of the three allowed values.
- Every `steps_json` cell parses as a JSON array.
- Each step has exactly the required seven keys.
- Step numbers start at 1 and are consecutive.
- Phases and operation order comply with the specification.
- Findings and COMPLETE verification cite valid participant-visible IDs.
- Proposed remediation/future verification for INCOMPLETE use `evidence_id: ""`.
- NOT_APPLICABLE has an empty array.
- No evidence after `audit_at` influences decisions.

## 4. Evaluation files
Create:
- `code/evaluation/evaluation_report.md`
- `code/evaluation/usage_report.md`

Reports must contain real metrics and actual run usage. Include at least three custom synthetic test cases. Do not place required evaluation details only in raw JSON/CSV/log files; write them in Markdown.

## 5. Packaging
From the repository root, package the runnable solution and reports without the dataset, virtual environments, caches, secrets, or nested archives.

Example for macOS/Linux, adjust paths only if your project layout differs:
```bash
zip -r code.zip README.md code \
  -x "*/__pycache__/*" "*/.venv/*" "*/venv/*" "*/node_modules/*" "*/.git/*" "*/.DS_Store" "*.zip" "*.tar" "*.gz"
```

On Windows, use PowerShell `Compress-Archive` with explicit paths, and inspect the resulting archive before submission. The official README's current packaging instructions take precedence if they differ.

## 6. Agent trace and chat transcript
- `log.txt` must follow the exact format in `AGENTS.md`, be append-only, and contain no secrets or real personal data.
- `agent_trace_instructions.md` describes packaging relevant Antigravity/other coding-agent traces. Include only relevant challenge sessions; do not copy the entire application data directory.
- Inspect trace contents before upload. Redact credentials, tokens, cookies, private keys, unrelated conversations, and sensitive personal information.
- Never include `.env`, authentication files, credential stores, or settings.
- Keep original structured transcript files where practical; do not replace them solely with screenshots or summaries if raw traces are required.

## 7. Final pre-submit checklist
- [ ] Full dataset run completed.
- [ ] Root `output.csv` validated and inspected.
- [ ] `code.zip` includes source, prompts/configuration, README, evaluation reports.
- [ ] `code.zip` excludes `dataset/`, virtualenvs, caches, nested archives, credentials.
- [ ] `log.txt` is the requested transcript and was not rewritten.
- [ ] Relevant agent trace ZIP is assembled if requested.
- [ ] Token/cost report matches actual instrumentation.
- [ ] At least three custom tests are documented.
- [ ] Interview answers are practiced.
- [ ] Submission portal and official deadline checked from official event information; do not infer a deadline from the repository alone.
