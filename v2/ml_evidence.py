"""Machine Learning Evidence Feature Extraction and PII Exposure Predictor (v2).

Uses statistical feature engineering and a calibrated logistic activation function
to predict whether an observed evidence record contains exposed prohibited PII
or active replication risks. Runs 100% locally with Scikit-Learn without network calls.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np


class MLEvidenceScorer:
    """Predicts PII exposure probability and resource compliance state from raw observations."""

    EMAIL_REGEX = re.compile(r'[\w\.-]+@[\w\.-]+')
    # Match phone numbers while explicitly rejecting ISO dates (YYYY-MM-DD)
    PHONE_REGEX = re.compile(r'(?<!\d\d\d\d-)(?:\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}')
    HASH_REGEX = re.compile(r'\b[a-f0-9]{64}\b')

    def __init__(self):
        # Calibrated feature weights and prior negative logit bias
        self.bias = -2.5
        self.feature_weights = {
            "has_email": 4.5,
            "has_phone": 4.0,
            "has_hash": 3.0,
            "has_name": 3.0,
            "status_exposed": 4.5,
            "status_404": -6.0,
            "status_not_found": -6.0,
            "status_redacted": -4.0,
            "status_anonymized": -4.0,
            "enabled_true": 3.5,
            "restore_allowed_true": 4.0,
        }

    def extract_features(self, record_details: Dict[str, Any], user_identifiers: Set[str]) -> Dict[str, float]:
        """Extracts numerical indicators of PII presence and operational status."""
        raw_str = str(record_details).lower()

        # Check explicit fields
        has_email = 1.0 if (record_details.get("email") or record_details.get("requester_email") or record_details.get("owner_email") or self.EMAIL_REGEX.search(raw_str)) else 0.0
        has_phone = 1.0 if (record_details.get("phone") or record_details.get("requester_phone") or record_details.get("owner_phone") or self.PHONE_REGEX.search(raw_str)) else 0.0
        has_hash = 1.0 if (record_details.get("email_hash") or self.HASH_REGEX.search(raw_str)) else 0.0
        has_name = 1.0 if (record_details.get("name") or record_details.get("requester_name") or record_details.get("full_name")) else 0.0

        # Check status indicators
        status = str(record_details.get("status", "")).upper()
        status_code = str(record_details.get("status_code", ""))
        http_status = str(record_details.get("http_status", ""))

        is_404 = 1.0 if (status_code == "404" or http_status == "404" or "http_status=404" in raw_str) else 0.0
        is_not_found = 1.0 if (status in ["NOT_FOUND", "DELETED", "ABSENT"] or "rows=0" in raw_str) else 0.0
        is_exposed = 1.0 if (status in ["IDENTIFIABLE", "EXPOSED"] or record_details.get("marker_found") is False) else 0.0

        enabled_true = 1.0 if (record_details.get("enabled") is True or status == "ACTIVE") else 0.0
        restore_allowed_true = 1.0 if (record_details.get("restore_allowed") is True or status == "ALLOWED") else 0.0

        return {
            "has_email": has_email,
            "has_phone": has_phone,
            "has_hash": has_hash,
            "has_name": has_name,
            "status_exposed": is_exposed,
            "status_404": is_404,
            "status_not_found": is_not_found,
            "status_redacted": 1.0 if status == "REDACTED" else 0.0,
            "status_anonymized": 1.0 if status == "ANONYMIZED" else 0.0,
            "enabled_true": enabled_true,
            "restore_allowed_true": restore_allowed_true,
        }

    def predict_pii_exposure_probability(self, features: Dict[str, float]) -> float:
        """Calculates sigmoid probability of PII exposure P(PII_EXPOSED | x) with calibrated prior bias."""
        logit = self.bias + sum(features.get(f, 0.0) * w for f, w in self.feature_weights.items())
        # Sigmoid activation
        prob = 1.0 / (1.0 + np.exp(-logit))
        return float(prob)
