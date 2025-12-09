import hashlib
import hmac
from app.config.settings import settings
from app.utils.exceptions import InvalidPaystackWebhookException


def verify_paystack_webhook(request_body: bytes, signature: str) -> bool:
    """
    Verify Paystack webhook signature.
    
    Args:
        request_body: Raw request body bytes
        signature: X-Paystack-Signature header value
    
    Returns:
        True if signature is valid
    
    Raises:
        InvalidPaystackWebhookException
    """
    # Compute HMAC-SHA512 of request body using secret key
    hash_object = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request_body,
        hashlib.sha512
    )
    
    computed_signature = hash_object.hexdigest()
    
    # Compare signatures
    if not hmac.compare_digest(computed_signature, signature):
        raise InvalidPaystackWebhookException("Webhook signature verification failed")
    
    return True
