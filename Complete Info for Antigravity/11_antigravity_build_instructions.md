# Google Antigravity — Build Instructions

## Can Antigravity be used?
Yes. The provided repository instructions explicitly list Google Antigravity among compatible coding agents. The repository also includes instructions for locating and packaging relevant Antigravity conversation traces. Follow the repository's `AGENTS.md` and `agent_trace_instructions.md` exactly.

## Recommended way to use it
1. Clone the challenge repository.
2. Open the **repository root** in Antigravity, not only the `code/` subfolder.
3. Before editing, instruct Antigravity to read `AGENTS.md`, `problem_statement.md`, `README.md`, and `agent_trace_instructions.md` in full.
4. Ensure it follows the append-only `log.txt` contract. Do not let it rewrite old entries or guess the tool/model names in the log.
5. Ask it to inspect participant-facing dataset files and evidence before designing the final implementation.
6. Implement in small phases, running tests after each phase.
7. Require it to show exact commands, test output, and changed files.
8. Review the generated `output.csv`, evaluation report, usage report, ZIP contents, and trace before submission.

## Initial prompt for Antigravity
Paste the following after opening the repository root:

---
You are the implementation agent for the HackerRank Orchestrate October 2026 challenge, "Ghost Data Still Exists".

Before doing any work:
1. Read `AGENTS.md`, `problem_statement.md`, `README.md`, and `agent_trace_instructions.md` completely.
2. Follow `AGENTS.md` exactly, including append-only `log.txt` session-start and per-turn logging. Use the exact coding harness and runtime model identifiers; never guess them.
3. Use only participant-facing files under `dataset/` for predictions. Never inspect or use organizer-only truth, generator internals, hidden labels, or case-family shortcuts.
4. Preserve the exact output contract: root `output.csv`, columns `case_id,deletion_status,steps_json`, one row per input request, sorted by `case_id`; allowed statuses and operations only; exact seven step keys; correct evidence references; valid JSON arrays; phase/operation ordering.
5. Respect `audit_at`; evidence after the cutoff must not affect a case decision.
6. Apply `deletion_rules.csv`, including retained records and tombstone rules. Do not treat reported workflow status as proof.
7. Keep `code.zip` free of `dataset/`, virtual environments, caches, nested archives, secrets, and credentials.
8. Include `code/evaluation/evaluation_report.md` and `code/evaluation/usage_report.md`. Use actual measured metrics, model calls, tokens, and cost; never invent them.

Work in phases:
A. Reconnaissance: inventory repository files, CSV schemas, evidence file formats, dependencies, and sample-output patterns. Report findings before changing code.
B. Design: propose modules and tests based on the actual data. Do not assume field names or evidence formats beyond the contract.
C. Implement deterministic ingestion, authorization, identity resolution, evidence parsing/indexing, temporal reconstruction, policy evaluation, data-flow/restore analysis, remediation planning, serialization, and validation.
D. Add bounded LLM/VLM use only where a measured need exists. Validate every model output; final decisions remain deterministic and evidence-grounded.
E. Test public samples and at least three custom synthetic cases. Diagnose errors by root cause rather than hardcoding case IDs.
F. Run all 518 requests, validate output, create the evaluation/usage reports, and package the submission.
G. Review the ZIP and trace artifacts for prohibited data and secrets.

Do not build a website unless the core CLI output and evaluation pass first. If time permits, a local read-only dashboard may be proposed as a separate optional feature.

At each phase, summarize files changed, commands run, test results, risks, and next steps. Never claim a test passed unless you ran it.
---

## Trace handling
The supplied `agent_trace_instructions.md` says Antigravity transcripts are typically located in the relevant conversation's `brain` folder, with the transcript at `.system_generated/logs/transcript.jsonl`. Copy only the complete relevant conversation folder(s) for this challenge into `agent-trace/antigravity/`, retain useful artifacts, and inspect for secrets/unrelated content before zipping. Paths can vary by Antigravity product/version; use the instructions in the supplied trace file as the source of truth.
