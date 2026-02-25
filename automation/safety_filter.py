import re

SENSITIVE_KEYWORDS = [
    "bank", "transfer", "account", "payment", "invoice",
    "contract", "legal", "deadline", "urgent", "asap",
    "money", "₦", "$", "usd", "naira",
    "otp", "code", "password"
]


def is_sensitive(message: str) -> bool:
    """
    Detect if a message contains sensitive content requiring confirmation.
    Returns True if message should be reviewed before sending.
    """
    if not message:
        return False
    
    text = message.lower()

    # Keyword detection
    for word in SENSITIVE_KEYWORDS:
        if word in text.lower():
            return True

    # Detect currency symbols
    if re.search(r"[₦$€£¥]", text):
        return True

    # Detect large numbers (4+ digits)
    if re.search(r"\b\d{4,}\b", text):
        return True

    return False
