"""Request intent classification module for Ghost Data Still Exists.

Determines whether a user request authorizes account/data deletion,
or is a non-deletion request (access, export, rectification, marketing opt-out,
security inquiry) which must be resolved as NOT_APPLICABLE with steps_json=[].
"""

import re
from typing import Tuple


NON_DELETION_PHRASES = [
    r"not\s+(?:asking\s+for|authoriz(?:e|ing)|requesting)\s+(?:deletion|account\s+closure|erasure)",
    r"information\s+request\s+only[;,]\s+do\s+not\s+delete",
    r"leave\s+(?:the|my)\s+account\s+active",
    r"keep\s+(?:the|my)\s+account\s+(?:open|intact|as\s+it\s+is)",
    r"do\s+not\s+(?:delete|close|modify)\s+(?:my|any)\s+(?:account|records|data|profile)",
    r"only\s+asking\s+for\s+data\s+access",
    r"not\s+a\s+request\s+to\s+erase",
    r"keep\s+my\s+customer\s+profile\s+and\s+transaction\s+history",
    r"without\s+removing\s+any\s+of\s+my\s+records",
    r"marketing\s+lists\s+only",
    r"continue\s+using\s+the\s+service",
    r"don't\s+delete\s+or\s+change\s+anything",
]

NON_DELETION_COMPILED = [re.compile(p, re.IGNORECASE) for p in NON_DELETION_PHRASES]


class RequestClassifier:
    """Classifies user request text to determine deletion authorization."""

    @staticmethod
    def is_authorized_deletion(request_text: str) -> Tuple[bool, str]:
        """
        Evaluates request text.
        
        Returns:
            (is_authorized, reason)
            is_authorized: True if this is an authorized deletion request.
                           False if this is a non-deletion request (NOT_APPLICABLE).
        """
        if not request_text or not isinstance(request_text, str):
            return False, "Empty request text"

        text = request_text.strip()

        # Check for explicit non-deletion patterns
        for pattern in NON_DELETION_COMPILED:
            if pattern.search(text):
                return False, f"Non-deletion intent detected by pattern: {pattern.pattern}"

        return True, "Authorized deletion request"
