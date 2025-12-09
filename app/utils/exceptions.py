from fastapi import HTTPException, status
from typing import Optional


class WalletException(HTTPException):
    """Base exception for wallet operations."""
    pass


class InsufficientBalanceException(WalletException):
    def __init__(self, message: str = "Insufficient balance for this operation"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


class InvalidAPIKeyException(WalletException):
    def __init__(self, message: str = "Invalid or expired API key"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


class MissingPermissionException(WalletException):
    def __init__(self, permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have '{permission}' permission"
        )


class APIKeyLimitExceededException(WalletException):
    def __init__(self, max_keys: int = 5):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {max_keys} active API keys allowed per user"
        )


class InvalidJWTException(WalletException):
    def __init__(self, message: str = "Invalid or expired JWT token"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


class UserNotFoundException(WalletException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


class WalletNotFoundException(WalletException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")


class TransactionNotFoundException(WalletException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")


class InvalidPaystackWebhookException(WalletException):
    def __init__(self, message: str = "Invalid Paystack webhook signature"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


class InvalidExpiryFormatException(WalletException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid expiry format. Use: 1H, 1D, 1M, or 1Y"
        )


class KeyNotExpiredException(WalletException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key has not expired yet"
        )


class InvalidRecipientException(WalletException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recipient wallet")
