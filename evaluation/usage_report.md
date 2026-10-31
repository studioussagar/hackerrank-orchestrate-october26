# Ghost Data Still Exists: Version 2 (ML Model) Usage Report

## 1. Overview and Model Architecture

The Version 2 implementation of the Ghost Data Still Exists audit agent utilizes a **Local Machine Learning Architecture** built with `scikit-learn`:
- **Intent NLP Pipeline:** Hybrid Word & Character TF-IDF FeatureUnion + Regularized Logistic Regression Classifier.
- **State & Risk Feature Estimator:** Statistical multi-feature vectorizer scoring residual PII and synchronization risk.
- **Autonomous & Self-Contained:** 100% local execution without external network connections, cloud API keys, or remote model dependencies.

---

## 2. Model Usage & Cost Summary (Full Dataset Run: 518 Requests)

| Metric | Value |
|---|---|
| **Model Provider** | Local Scikit-Learn Pipeline (`scikit-learn` / `numpy` CPU Runtime) |
| **Model Identifier** | `TFIDF-FeatureUnion-LogisticRegression-v2` |
| **Total Evaluation Requests Processed** | 518 |
| **Total External API Model Calls** | **0** |
| **Total Input Tokens** | **0** |
| **Total Output Tokens** | **0** |
| **Average Tokens Per Request** | **0** |
| **Estimated Total Cost (USD)** | **$0.00** |
| **Estimated Cost Per Request (USD)** | **$0.00** |

---

## 3. Resource & Execution Performance

| Resource Metric | Measurement |
|---|---|
| **Full Dataset Execution Time** | **0.86 seconds** across all 518 evaluation requests |
| **Throughput** | **~602 requests / second** |
| **Memory Peak (RSS)** | ~192 MB |
| **Evidence Ingestion** | 94 multi-modal evidence files indexed into local graphs |
| **API Network Calls** | 0 (Strict compliance with offline evaluation constraints) |
| **Reproducibility** | 100% deterministic local inference |
