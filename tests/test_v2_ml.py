"""Unit and integration tests for Version 2 ML-based deletion audit agent."""

import pytest
from v2.ml_classifier import MLIntentClassifier
from v2.ml_evidence import MLEvidenceScorer


def test_ml_intent_classifier_separation():
    """Verifies that the ML classifier cleanly separates deletion and non-deletion intents."""
    clf = MLIntentClassifier()

    deletion_texts = [
        "Please permanently delete my account and all associated personal data.",
        "Intenté eliminar mi cuenta ayer, pero la página terminó mostrando un error. ¿Pueden eliminarla manualmente?",
        "Je demande la suppression définitive du compte associé à cette adresse e-mail.",
        "アカウントとすべての個人データを完全に削除してください。",
        "I want to close this account permanently and erase all my search history.",
    ]

    non_deletion_texts = [
        "Please provide an export of my account data in JSON format so I can review what information you have stored.",
        "Please update my account contact preferences to SMS only and remove my email from all marketing lists.",
        "Please change the email address used for this account. I want to keep the account open.",
        "The mobile number on my profile is out of date. Please replace it with my new number. Keep my account open.",
        "Je vous écris pour demander une copie complète de mes données personnelles en vertu de l'article 15 du RGPD.",
    ]

    for dt in deletion_texts:
        is_auth, prob, label = clf.is_authorized_deletion(dt)
        assert is_auth is True, f"Failed deletion text: {dt} (prob={prob:.4f})"
        assert prob >= 0.35, f"Probability too low for deletion: {prob:.4f}"
        assert label == "AUTHORIZED_DELETION"

    for ndt in non_deletion_texts:
        is_auth, prob, label = clf.is_authorized_deletion(ndt)
        assert is_auth is False, f"Failed non-deletion text: {ndt} (prob={prob:.4f})"
        assert prob < 0.35, f"Probability too high for non-deletion: {prob:.4f}"
        assert label == "NON_DELETION_ACCESS_OPT_OUT"


def test_ml_evidence_scorer_risk():
    """Verifies that MLEvidenceScorer accurately scores exposed PII vs redacted tombstones."""
    scorer = MLEvidenceScorer()

    all_idents = {"user_123", "alice@example.com", "+1-555-0100", "Alice Smith"}

    # Exposed PII state
    exposed_state = {
        "status": "EXPOSED",
        "email": "alice@example.com",
        "phone": "+1-555-0100",
        "name": "Alice Smith"
    }
    feats_exposed = scorer.extract_features(exposed_state, all_idents)
    prob_exposed = scorer.predict_pii_exposure_probability(feats_exposed)
    assert prob_exposed > 0.80, f"Expected high PII probability, got {prob_exposed}"

    # Redacted tombstone state
    redacted_state = {
        "status": "REDACTED",
        "user_id": "user_123",
        "email": None,
        "phone": None,
        "name": None
    }
    feats_redacted = scorer.extract_features(redacted_state, all_idents)
    prob_redacted = scorer.predict_pii_exposure_probability(feats_redacted)
    assert prob_redacted < 0.20, f"Expected low PII probability, got {prob_redacted}"
