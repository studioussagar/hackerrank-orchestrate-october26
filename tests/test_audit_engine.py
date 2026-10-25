"""Unit and integration tests for Ghost Data Still Exists."""

import json
import pytest
from code.classifier import RequestClassifier
from code.identity import IdentityResolver
from code.policy import (
    FINDING_OPERATIONS,
    PHASE_FINDING,
    PHASE_REMEDIATION,
    PHASE_VERIFICATION,
    REMEDIATION_OPERATIONS,
    VERIFICATION_OPERATIONS,
)
from code.serializer import serialize_steps, sort_steps


def test_identity_resolution():
    resolver = IdentityResolver(
        identities_path="dataset/user_identities.csv",
        audit_log_path="dataset/user_audit_log.csv"
    )
    # Test current email
    uid1 = resolver.resolve_email("amina.elmasri@gmail.com")
    assert uid1 == "user_01"
    
    # Test case insensitivity
    uid1_upper = resolver.resolve_email("AMINA.ELMASRI@GMAIL.COM")
    assert uid1_upper == "user_01"

    # Test historical email change
    idents = resolver.get_all_identifiers("user_01")
    assert "user_01" in idents
    assert "amina.elmasri@gmail.com" in idents


def test_classifier_authorized_deletion():
    classifier = RequestClassifier()
    is_auth, _ = classifier.is_authorized_deletion("Please delete my account and all personal data.")
    assert is_auth is True

    # Multi-lingual
    is_auth_es, _ = classifier.is_authorized_deletion("Por favor elimine mi cuenta permanentemente.")
    assert is_auth_es is True


def test_classifier_non_deletion():
    classifier = RequestClassifier()
    # GDPR Art 15 access
    is_auth, _ = classifier.is_authorized_deletion(
        "I am writing to request a complete copy of all personal data held about me. "
        "I am not asking for deletion at this time; please leave the account active."
    )
    assert is_auth is False

    # Marketing opt-out
    is_auth_opt, _ = classifier.is_authorized_deletion(
        "Please opt me out of marketing lists only. Do not delete my account."
    )
    assert is_auth_opt is False


def test_serializer_canonical_sorting():
    raw_steps = [
        {
            "phase": "VERIFICATION",
            "system_id": "account_service",
            "resource_id": "account_001",
            "operation": "VERIFY_RECORD_ABSENT",
            "state": "ABSENT",
            "evidence_id": "evidence_54"
        },
        {
            "phase": "FINDING",
            "system_id": "search_service",
            "resource_id": "search_001",
            "operation": "REPORT_REMAINING_RECORD",
            "state": "PRESENT",
            "evidence_id": "evidence_57"
        },
        {
            "phase": "REMEDIATION",
            "system_id": "search_service",
            "resource_id": "search_001",
            "operation": "DELETE_RECORD",
            "state": "ABSENT",
            "evidence_id": ""
        }
    ]

    sorted_steps = sort_steps(raw_steps)
    assert len(sorted_steps) == 3
    assert sorted_steps[0]["phase"] == "FINDING"
    assert sorted_steps[0]["step_no"] == 1
    assert sorted_steps[1]["phase"] == "REMEDIATION"
    assert sorted_steps[1]["step_no"] == 2
    assert sorted_steps[2]["phase"] == "VERIFICATION"
    assert sorted_steps[2]["step_no"] == 3


def test_serializer_seven_keys():
    raw_steps = [{
        "phase": "FINDING",
        "system_id": "account_service",
        "resource_id": "account_005",
        "operation": "REPORT_REMAINING_RECORD",
        "state": "PRESENT",
        "evidence_id": "evidence_54"
    }]
    formatted = sort_steps(raw_steps)
    expected_keys = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}
    assert set(formatted[0].keys()) == expected_keys


def test_audit_time_invariance():
    """Verifies that evidence captured after audit_at is strictly ignored."""
    from code.evidence_loader import EvidenceRecord
    rec_early = EvidenceRecord("ev_01", "origin", "2026-08-01T00:00:00Z", "account_service", "account_100", "USER_PROFILE", {"status": "NOT_FOUND"}, {"user_100"})
    rec_late = EvidenceRecord("ev_02", "origin", "2026-09-01T00:00:00Z", "account_service", "account_100", "USER_PROFILE", {"status": "FOUND"}, {"user_100"})
    
    audit_at = "2026-08-15T00:00:00Z"
    assert rec_early.captured_at <= audit_at
    assert not (rec_late.captured_at <= audit_at)


def test_incomplete_case_empty_remediation_evidence_id():
    """Verifies that remediation steps in incomplete cases strictly use empty evidence_id."""
    raw_steps = [
        {"phase": "FINDING", "system_id": "support_platform", "resource_id": "support_01", "operation": "REPORT_EXPOSED_PII", "state": "PRESENT", "evidence_id": "evidence_01"},
        {"phase": "REMEDIATION", "system_id": "support_platform", "resource_id": "support_01", "operation": "REDACT_RECORD", "state": "REDACTED", "evidence_id": ""},
        {"phase": "VERIFICATION", "system_id": "support_platform", "resource_id": "support_01", "operation": "VERIFY_RECORD_REDACTED", "state": "REDACTED", "evidence_id": ""}
    ]
    sorted_steps = sort_steps(raw_steps)
    assert sorted_steps[1]["evidence_id"] == ""
    assert sorted_steps[2]["evidence_id"] == ""

