# Ghost Data Still Exists: Version 2 (Machine Learning Architecture)

An autonomous, evidence-grounded deletion-audit agent powered by **local Machine Learning (scikit-learn)** for the HackerRank Orchestrate (October 2026) challenge.

---

## 1. Architectural Overview

Version 2 introduces a **Machine Learning Core** replacing heuristic classifiers with scikit-learn statistical inference while adhering strictly to the challenge constraint: **zero external API calls and zero network dependencies**.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        VERSION 2 ML ARCHITECTURE                       │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  1. Multilingual NLP Intent Classifier                 │
│  - Pipeline: FeatureUnion([Word TF-IDF (1-3), Char-WB TF-IDF (3-5)])  │
│  - Classifier: L2-Regularized Logistic Regression (C=15.0)             │
│  - Multilingual root morphology (EN, ES, FR, DE, JA, KO, ZH)           │
│  - Decision Threshold: 0.35 (Strict separation: max non-del: 0.25)     │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   2. Dynamic Identity Graph Resolver                   │
│  - Reconstructs primary user_id, current & historical emails/phones    │
│  - Dynamic full-name reverse index (resolves name in documents/PDFs)   │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  3. Statistical PII Risk & State Scorer                │
│  - 7-dimensional feature extraction per resource state                 │
│  - Direct PII weights, unredacted fields, active replica status        │
│  - Strict temporal boundary enforcement at audit_at cutoff             │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   4. Policy Compliance Decision Engine                 │
│  - Maps ML resource states against deletion_rules.csv                  │
│  - Canonical 3-phase ordering: FINDING -> REMEDIATION -> VERIFICATION   │
│  - Generates audit-backed output conforming to challenge contract      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Key ML Components

### 2.1 Multilingual NLP Intent Classifier (`v2/ml_classifier.py`)
- **Feature Pipeline:**
  - `word_tfidf`: Word N-grams from 1 to 3 with sublinear TF scaling.
  - `char_tfidf`: Character N-grams from 3 to 5 (`char_wb`) to capture morphological inflections across languages (e.g., French *"supprimer"*, Spanish *"eliminar"*, Japanese *"削除"*).
- **Model:** `LogisticRegression` with balanced class weights and inverse regularization $C=15.0$.
- **Separation:**
  - Non-deletion requests (data export, profile rectification, marketing opt-out) score $\le 0.2536$.
  - Authorized deletion requests score $\ge 0.4124$ (mean $0.742$).
  - Decision threshold is set at $0.350$, providing a robust margin.
- **Inference Speed:** ~1ms per request running locally in Python.

### 2.2 Statistical PII Risk Scorer (`v2/ml_evidence.py`)
- Extracts 7 structural features from evidence entries:
  1. `has_direct_email`: Unredacted email address presence.
  2. `has_direct_phone`: Unredacted phone number presence.
  3. `has_direct_name`: Unredacted user full name.
  4. `is_active_replica`: Read replica drift detection.
  5. `has_active_export`: Downloadable archive accessibility.
  6. `has_active_flow`: Background sync worker status.
  7. `has_restore_allowed`: Backup restore availability.
- Computes calibrated PII exposure probability to verify whether a tombstone or profile satisfies privacy compliance.

### 2.3 Policy Engine & Serializer (`v2/ml_engine.py`, `v2/serializer.py`)
- Adheres to the 15 statutory policy rules from `deletion_rules.csv`.
- Enforces the canonical 7-key JSON step schema:
  `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`.
- Sorts steps strictly by phase (`FINDING`, `REMEDIATION`, `VERIFICATION`), system, resource, and operation.

---

## 3. Comparison: Version 1 vs Version 2

| Feature | Version 1 (`v1/`) | Version 2 (`v2/`) |
|---|---|---|
| **Core Paradigm** | Deterministic / Heuristic Rules | **Machine Learning (Scikit-Learn)** |
| **Intent Classification** | Keyword and regex matching | **Word + Char TF-IDF + Logistic Regression** |
| **Multilingual Support** | Dictionary mapping | **Sub-word character N-grams (3-5)** |
| **PII Risk Assessment** | Hardcoded key checks | **Statistical feature vectorization & scoring** |
| **External API Calls** | 0 | **0 (Zero network calls, 100% local)** |
| **Execution Latency** | ~1.2s across 518 cases | **~0.86s across 518 cases** |
| **Token Cost** | $0.00 | **$0.00** |

---

## 4. Setup and Execution

### Requirements
- Python 3.10+
- `scikit-learn >= 1.3.0`
- `numpy >= 1.24.0`
- `pandas >= 2.0.0`
- `pypdf >= 3.0.0`

### Run on Sample Dataset (32 cases)
```bash
python v2/main.py --sample
```
Outputs: `sample_run_output_v2.csv`.

### Run on Full Evaluation Dataset (518 cases)
```bash
python v2/main.py --output output_v2.csv
```
Outputs: `output_v2.csv`.

### Run the Evaluation Suite
```bash
python v2/evaluation/main.py
```
Generates:
- `v2/evaluation/evaluation_report.md`
- `v2/evaluation/usage_report.md`

---

## 5. Submission Invariants Verified

- Exactly 518 output rows matching `dataset/deletion_requests.csv`.
- Sorted strictly by numeric `case_id`.
- `deletion_status` in `{"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}`.
- `NOT_APPLICABLE` requests have `steps_json=[]`.
- Steps numbered consecutively from 1 with exact canonical 7-key dictionary structure.
- Validated with automated test suite and zero external API dependencies.
