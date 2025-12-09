import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import settings
from app.models import Transaction, Wallet, TransactionStatus, PaystackWebhookLog
from app.utils.exceptions import WalletNotFoundException, TransactionNotFoundException
from datetime import datetime
from typing import Optional
from uuid import UUID
import json


class PaystackService:
    """Service for handling Paystack API interactions."""
    
    def __init__(self):
        self.base_url = settings.PAYSTACK_BASE_URL
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
    
    async def initialize_transaction(
        self,
        email: str,
        amount: float,
        reference: str,
        meta: Optional[dict] = None,
    ) -> dict:
        """
        Initialize a Paystack transaction.
        
        Args:
            email: Customer email
            amount: Amount in kobo (multiply by 100)
            reference: Unique transaction reference
            meta: Additional metadata
        
        Returns:
            dict with authorization_url and other details
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "email": email,
            "amount": int(amount * 100),  # Convert to kobo
            "reference": reference,
            "metadata": meta or {},
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=headers,
            )
            
            if response.status_code != 200:
                raise Exception(f"Paystack error: {response.text}")
            
            return response.json()
    
    async def verify_transaction(self, reference: str) -> dict:
        """
        Verify a Paystack transaction.
        
        Args:
            reference: Transaction reference
        
        Returns:
            dict with transaction status and details
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=headers,
            )
            
            if response.status_code != 200:
                raise Exception(f"Paystack error: {response.text}")
            
            return response.json()


async def get_transaction_by_reference(
    reference: str,
    session: AsyncSession,
) -> Transaction:
    """Get transaction by Paystack reference."""
    result = await session.execute(
        select(Transaction).where(Transaction.reference == reference)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise TransactionNotFoundException()
    
    return transaction


async def credit_wallet(
    transaction_id: UUID,
    session: AsyncSession,
) -> Transaction:
    """
    Credit wallet for a successful deposit.
    
    Args:
        transaction_id: Transaction ID to credit
        session: AsyncSession
    
    Returns:
        Updated Transaction object
    
    Raises:
        TransactionNotFoundException
        WalletNotFoundException
    """
    # Get transaction
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise TransactionNotFoundException()
    
    # Get wallet
    result = await session.execute(
        select(Wallet).where(Wallet.id == transaction.wallet_id)
    )
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        raise WalletNotFoundException()
    
    # Update wallet balance
    wallet.balance += transaction.amount
    wallet.updated_at = datetime.utcnow()
    
    # Update transaction status
    transaction.status = TransactionStatus.SUCCESS
    transaction.updated_at = datetime.utcnow()
    
    await session.flush()
    return transaction


async def mark_webhook_processed(
    webhook_log_id: UUID,
    session: AsyncSession,
) -> PaystackWebhookLog:
    """Mark a webhook as processed."""
    result = await session.execute(
        select(PaystackWebhookLog).where(PaystackWebhookLog.id == webhook_log_id)
    )
    webhook_log = result.scalar_one_or_none()
    
    if webhook_log:
        webhook_log.processed = True
    
    await session.flush()
    return webhook_log


async def get_or_create_webhook_log(
    event: str,
    reference: Optional[str],
    payload: dict,
    session: AsyncSession,
) -> PaystackWebhookLog:
    """Get existing webhook log or create a new one."""
    # Check if already processed
    if reference:
        result = await session.execute(
            select(PaystackWebhookLog).where(
                PaystackWebhookLog.reference == reference,
                PaystackWebhookLog.event == event,
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
    
    # Create new log
    webhook_log = PaystackWebhookLog(
        event=event,
        reference=reference,
        payload=payload,
        processed=False,
    )
    session.add(webhook_log)
    await session.flush()
    return webhook_log


async def get_deposit_status(
    reference: str,
    session: AsyncSession,
) -> dict:
    """
    Get deposit status for a transaction.
    
    Args:
        reference: Paystack reference
        session: AsyncSession
    
    Returns:
        dict with status, amount, and reference
    """
    transaction = await get_transaction_by_reference(reference, session)
    
    return {
        "reference": transaction.reference,
        "status": transaction.status.value,
        "amount": transaction.amount,
    }
