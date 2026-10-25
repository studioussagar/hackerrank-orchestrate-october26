# Optional Web Dashboard — UX and Design Specification

## Decision
A website is **not required** by the challenge. The scoring contract is a terminal-run agent that produces `output.csv`. Implement the CLI first. A dashboard is a stretch goal only after all core acceptance criteria pass.

## 1. Product purpose
Provide a local read-only interface for inspecting audit runs, case decisions, evidence citations, policy findings, and proposed remediation. The UI must not execute destructive operations.

## 2. Target users
- Privacy/compliance analyst reviewing a case.
- Engineer validating remediation.
- Evaluator inspecting why a decision was made.

## 3. Primary screens
### A. Run Overview
- Total cases.
- Counts by COMPLETE / INCOMPLETE / NOT_APPLICABLE.
- Input parse warnings.
- Contract validation status.
- Last run time and output file location.
- Do not expose raw PII in overview cards.

### B. Case Explorer
- Search by case ID and permitted identifier.
- Filters by status, system, category, and risk type.
- Table columns: case ID, status, finding count, recreation-risk count, verification count.
- Avoid displaying full email/phone by default.

### C. Case Detail
- Summary decision and cutoff (`audit_at`).
- Identity timeline with masked identifiers.
- Findings grouped by system/resource.
- Evidence panel with evidence ID, source, timestamp, extraction method, and concise excerpt.
- Data-flow/restore graph.
- Policy rule and required treatment.
- Ordered remediation plan and verification checklist.
- Clear badge distinguishing observed evidence from proposed future actions.

### D. Evidence Viewer
- Text/JSON/log preview with line numbers.
- PDF/image preview only if local safe rendering is available.
- Show file origin, capture time, parser/OCR status.
- Do not treat the evidence manifest alone as proof.

### E. Evaluation
- Public sample metrics.
- Custom test pass/fail.
- Output contract checks.
- Token/cost summary if models were used.
- Avoid implying hidden-set accuracy when no reference exists.

## 4. Navigation
Left navigation:
- Overview
- Cases
- Evidence
- Data Flows
- Evaluation
- Settings / Run Information

## 5. Design system
- Style: clean, restrained, evidence-oriented, enterprise compliance tool.
- Layout: desktop-first responsive application; readable on tablet.
- Typography: system sans-serif; monospace for IDs, timestamps, JSON.
- Color use: do not rely on color alone. Use text labels and icons.
  - COMPLETE: green status plus label.
  - INCOMPLETE: amber/red status plus label.
  - NOT_APPLICABLE: neutral gray plus label.
  - Evidence-backed: solid badge.
  - Proposed action: outlined badge.
  - Parse failure/uncertainty: visible warning with explanatory text.
- Use clear spacing, thin dividers, and dense but scannable tables.
- Avoid decorative charts that do not improve auditability.

## 6. Interaction requirements
- Selecting a case opens its detail view.
- Clicking an evidence ID opens the evidence item and source locator.
- Clicking a system/resource in the graph filters related evidence.
- Sort and filter tables without mutating the underlying output.
- Export the same validated `output.csv`; do not alter schema.
- Show warnings if a case lacks enough evidence to support COMPLETE.
- Copy JSON step array for debugging.

## 7. Accessibility and privacy
- Keyboard accessible navigation and tables.
- Visible focus states and semantic headings.
- WCAG AA contrast target.
- Mask direct identifiers by default.
- No public hosting or external telemetry for challenge data.
- Do not send evidence to third-party analytics.
- No destructive controls.

## 8. Suggested optional stack
If built: React + TypeScript + Vite for the frontend, and a small FastAPI backend reading local run artifacts. Keep backend read-only. Do not add a database unless necessary. The CLI remains the source of truth.

## 9. Definition of done
- Dashboard reads a completed run and does not change prediction logic.
- It shows evidence provenance and time cutoff.
- It makes evidence vs proposed action visually distinct.
- It does not expose unnecessary PII.
- It can be omitted entirely without affecting the scored submission.
