from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models import (
    User,
    Wallet,
    Transaction,
    APIKey,
    TransactionType,
    TransactionStatus,
)
from app.utils.exceptions import (
    WalletNotFoundException,
    InsufficientBalanceException,
    InvalidRecipientException,
    APIKeyLimitExceededException,
    KeyNotExpiredException,
)
from app.utils.security import generate_api_key, hash_api_key, parse_expiry
from app.config.settings import settings
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
import secrets
import string


async def get_or_create_wallet(user: User, session: AsyncSession) -> Wallet:
    """Get user's wallet or create one if doesn't exist."""
    # Check if wallet exists
    result = await session.execute(
        select(Wallet).where(Wallet.user_id == user.id)
    )
    wallet = result.scalar_one_or_none()
    
    if wallet:
        return wallet
    
    # Create new wallet
    wallet_number = generate_wallet_number()
    wallet = Wallet(
        user_id=user.id,
        wallet_number=wallet_number,
        balance=0.0,
        currency="NGN",
    )
    session.add(wallet)
    await session.flush()
    await session.commit() 
    await session.refresh(wallet) 
    return wallet


def generate_wallet_number() -> str:
    """Generate unique 13-digit wallet number."""
    # Could use a more sophisticated algorithm
    return "".join(secrets.choice(string.digits) for _ in range(13))


async def get_wallet_balance(wallet_id: UUID, session: AsyncSession) -> float:
    """Get current wallet balance."""
    result = await session.execute(
        select(Wallet).where(Wallet.id == wallet_id)
    )
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        raise WalletNotFoundException()
    
    return wallet.balance


async def get_transaction_history(
    user_id: UUID,
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> tuple:
    """Get transaction history for a user."""
    # Get transactions
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    transactions = result.scalars().all()
    
    # Get total count
    count_result = await session.execute(
        select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
    )
    total_count = count_result.scalar()
    
    return transactions, total_count


async def create_transaction(
    user_id: UUID,
    wallet_id: UUID,
    transaction_type: TransactionType,
    amount: float,
    session: AsyncSession,
    status: TransactionStatus = TransactionStatus.PENDING,
    reference: Optional[str] = None,
    recipient_wallet_id: Optional[UUID] = None,
    description: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Transaction:
    """Create a new transaction record."""
    transaction = Transaction(
        user_id=user_id,
        wallet_id=wallet_id,
        type=transaction_type,
        amount=amount,
        status=status,
        reference=reference,
        recipient_wallet_id=recipient_wallet_id,
        description=description,
        meta=meta or {},
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def transfer_funds(
    sender_user: User,
    recipient_wallet_number: str,
    amount: float,
    session: AsyncSession,
) -> Transaction:
    """
    Transfer funds from sender's wallet to recipient's wallet.
    
    Args:
        sender_user: Sender User object
        recipient_wallet_number: Recipient's wallet number
        amount: Amount to transfer
        session: AsyncSession for database
    
    Returns:
        Transaction object
    
    Raises:
        WalletNotFoundException
        InsufficientBalanceException
        InvalidRecipientException
    """
    # Get sender's wallet
    result = await session.execute(
        select(Wallet).where(Wallet.user_id == sender_user.id)
    )
    sender_wallet = result.scalar_one_or_none()
    
    if not sender_wallet:
        raise WalletNotFoundException()
    
    # Check balance
    if sender_wallet.balance < amount:
        raise InsufficientBalanceException()
    
    # Get recipient's wallet
    result = await session.execute(
        select(Wallet).where(Wallet.wallet_number == recipient_wallet_number)
    )
    recipient_wallet = result.scalar_one_or_none()
    
    if not recipient_wallet:
        raise InvalidRecipientException()
    
    # Prevent self-transfer
    if sender_wallet.id == recipient_wallet.id:
        raise InvalidRecipientException()
    
    # Perform transfer (atomic)
    sender_wallet.balance -= amount
    recipient_wallet.balance += amount
    sender_wallet.updated_at = datetime.utcnow()
    recipient_wallet.updated_at = datetime.utcnow()
    
    # Record transaction
    transaction = await create_transaction(
        user_id=sender_user.id,
        wallet_id=sender_wallet.id,
        transaction_type=TransactionType.TRANSFER,
        amount=amount,
        status=TransactionStatus.SUCCESS,
        recipient_wallet_id=recipient_wallet.id,
        description=f"Transfer to wallet {recipient_wallet_number}",
        session=session,
    )
    
    await session.flush()
    return transaction


# ============== API Key Management ==============

async def create_api_key(
    user_id: UUID,
    name: str,
    permissions: List[str],
    expiry_str: str,
    session: AsyncSession,
) -> tuple:
    """
    Create a new API key.
    
    Args:
        user_id: User ID
        name: Key name
        permissions: List of permissions
        expiry_str: Expiry string (1H, 1D, 1M, 1Y)
        session: AsyncSession
    
    Returns:
        Tuple of (api_key_string, api_key_object)
    
    Raises:
        APIKeyLimitExceededException
        InvalidExpiryFormatException
    """
    # Check active key count
    result = await session.execute(
        select(func.count(APIKey.id)).where(
            and_(
                APIKey.user_id == user_id,
                APIKey.is_active == True,
                APIKey.is_revoked == False,
                APIKey.expires_at > datetime.utcnow(),
            )
        )
    )
    active_count = result.scalar() or 0
    
    if active_count >= settings.API_KEY_MAX_ACTIVE:
        raise APIKeyLimitExceededException(settings.API_KEY_MAX_ACTIVE)
    
    # Parse expiry
    expires_at = parse_expiry(expiry_str)
    
    # Generate API key
    api_key_string = generate_api_key()
    key_hash = hash_api_key(api_key_string)
    
    # Create database record
    api_key = APIKey(
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        permissions=permissions,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.flush()
    
    return api_key_string, api_key


async def rollover_api_key(
    user_id: UUID,
    expired_key_id: UUID,
    new_expiry_str: str,
    session: AsyncSession,
) -> tuple:
    """
    Create a new API key from an expired one.
    
    Args:
        user_id: User ID
        expired_key_id: ID of expired API key
        new_expiry_str: New expiry string (1H, 1D, 1M, 1Y)
        session: AsyncSession
    
    Returns:
        Tuple of (api_key_string, api_key_object)
    
    Raises:
        KeyNotExpiredException
        InvalidExpiryFormatException
    """
    # Get the expired key
    result = await session.execute(
        select(APIKey).where(
            and_(APIKey.id == expired_key_id, APIKey.user_id == user_id)
        )
    )
    old_key = result.scalar_one_or_none()
    
    if not old_key:
        raise KeyNotExpiredException()
    
    # Check if truly expired
    if old_key.expires_at > datetime.utcnow():
        raise KeyNotExpiredException()
    
    # Reuse permissions
    permissions = old_key.permissions
    
    # Parse new expiry
    expires_at = parse_expiry(new_expiry_str)
    
    # Generate new API key
    api_key_string = generate_api_key()
    key_hash = hash_api_key(api_key_string)
    
    # Create new record
    new_key = APIKey(
        user_id=user_id,
        key_hash=key_hash,
        name=old_key.name,
        permissions=permissions,
        expires_at=expires_at,
    )
    session.add(new_key)
    
    # Mark old key as revoked
    old_key.is_revoked = True
    old_key.updated_at = datetime.utcnow()
    
    await session.flush()
    return api_key_string, new_key


async def list_api_keys(
    user_id: UUID,
    session: AsyncSession,
) -> List[APIKey]:
    """Get all API keys for a user."""
    result = await session.execute(
        select(APIKey)
        .where(APIKey.user_id == user_id)
        .order_by(APIKey.created_at.desc())
    )
    return result.scalars().all()


async def revoke_api_key(
    user_id: UUID,
    key_id: UUID,
    session: AsyncSession,
) -> APIKey:
    """Revoke an API key."""
    result = await session.execute(
        select(APIKey).where(
            and_(APIKey.id == key_id, APIKey.user_id == user_id)
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise WalletNotFoundException()
    
    api_key.is_revoked = True
    api_key.is_active = False
    api_key.updated_at = datetime.utcnow()
    
    await session.flush()
    return api_key
