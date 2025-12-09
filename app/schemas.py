from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from uuid import UUID


# ============== Auth Schemas ==============

class GoogleUserInfo(BaseModel):
    id: str
    email: str
    name: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============== User Schemas ==============

class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    google_id: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== Wallet Schemas ==============

class WalletBase(BaseModel):
    wallet_number: str
    currency: str = "NGN"


class WalletResponse(BaseModel):
    id: UUID
    wallet_number: str
    balance: float
    currency: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    balance: float
    currency: str = "NGN"


# ============== Transaction Schemas ==============

class TransactionResponse(BaseModel):
    id: UUID
    type: str
    amount: float
    status: str
    reference: Optional[str]
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    transactions: List[TransactionResponse]
    count: int


# ============== Paystack Schemas ==============

class DepositRequest(BaseModel):
    amount: float


class DepositResponse(BaseModel):
    reference: str
    authorization_url: str
    amount: float


class DepositStatusResponse(BaseModel):
    reference: str
    status: str
    amount: float


class PaystackWebhookData(BaseModel):
    event: str
    data: dict


# ============== Transfer Schemas ==============

class TransferRequest(BaseModel):
    wallet_number: str
    amount: float


class TransferResponse(BaseModel):
    status: str
    message: str
    transaction_id: Optional[UUID] = None


# ============== API Key Schemas ==============

class CreateAPIKeyRequest(BaseModel):
    name: str
    permissions: List[str]  # ["deposit", "transfer", "read"]
    expiry: str  # "1H", "1D", "1M", "1Y"


class CreateAPIKeyResponse(BaseModel):
    api_key: str
    expires_at: datetime
    key_id: UUID


class RolloverAPIKeyRequest(BaseModel):
    expired_key_id: UUID
    expiry: str


class RolloverAPIKeyResponse(BaseModel):
    api_key: str
    expires_at: datetime


class APIKeyListItem(BaseModel):
    id: UUID
    name: str
    permissions: List[str]
    is_active: bool
    is_revoked: bool
    expires_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyListItem]
    count: int


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    detail: str
    status_code: int = 400
