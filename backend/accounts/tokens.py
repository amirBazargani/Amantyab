"""Email verification token generation and verification using TimestampSigner."""

import logging
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

logger = logging.getLogger("amanatyab.accounts")

EMAIL_VERIFICATION_SALT = "accounts.tokens.email_verification"
EMAIL_VERIFICATION_MAX_AGE = 86400  # 24 hours in seconds


def generate_verification_token(user):
    """Generate a timestamped signed verification token for the given user."""
    signer = TimestampSigner(salt=EMAIL_VERIFICATION_SALT)
    return signer.sign(str(user.pk))


def verify_token(token, max_age=EMAIL_VERIFICATION_MAX_AGE):
    """
    Verify the token and return (user, error_code).
    error_code is None on success, or one of: 'expired', 'invalid', 'user_not_found'.
    """
    signer = TimestampSigner(salt=EMAIL_VERIFICATION_SALT)
    try:
        user_id = signer.unsign(token, max_age=max_age)
    except SignatureExpired:
        logger.warning("Email verification token expired: token=%s", token[:10] + "...")
        return None, "expired"
    except BadSignature:
        logger.warning("Email verification token invalid: token=%s", token[:10] + "...")
        return None, "invalid"

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        return user, None
    except User.DoesNotExist:
        logger.warning("Email verification user not found: user_id=%s", user_id)
        return None, "user_not_found"
