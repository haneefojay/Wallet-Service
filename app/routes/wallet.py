from fastapi import APIRouter, Depends, Request, Query
from fastapi.security import HTTPBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.database import get_db
from app.middleware.auth import get_authenticated_user

# Security schemes (optional - auto_error=False allows API key auth)
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
from app.services.wallet import (
    get_or_create_wallet,
    get_wallet_balance,
    get_transaction_history,
    transfer_funds,
    create_transaction,
)
from app.services.paystack import (
    PaystackService,
    get_transaction_by_reference,
    get_deposit_status,
)
from app.models import TransactionType, TransactionStatus
from app.schemas import (
    DepositRequest,
    DepositResponse,
    DepositStatusResponse,
    BalanceResponse,
    TransferRequest,
    TransferResponse,
    TransactionHistoryResponse,
)
from datetime import datetime
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/wallet", tags=["wallet"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/deposit", response_model=DepositResponse)
@limiter.limit("10/minute")  # Max 10 deposits per minute per IP
async def deposit(
    request: Request,
    payload: DepositRequest,
    session: AsyncSession = Depends(get_db),
    token: str = Depends(security),
    api_key: str = Depends(api_key_header),
):
    """
    Initiate a wallet deposit using Paystack.
    
    Args:
        payload: DepositRequest with amount
        session: Database session
    
    Returns:
        DepositResponse with authorization_url and reference
    """
    # Check permission if API key
    if request.headers.get("x-api-key"):
        auth_context = await get_authenticated_user(request, required_permission="deposit")
    else:
        auth_context = await get_authenticated_user(request)
    
    # Get or create wallet
    wallet = await get_or_create_wallet(auth_context.user, session)
    await session.refresh(wallet)
    
    # Create transaction record (pending)
    reference = f"paystack_{uuid.uuid4().hex[:12]}"
    transaction = await create_transaction(
        user_id=auth_context.user.id,
        wallet_id=wallet.id,
        transaction_type=TransactionType.DEPOSIT,
        amount=payload.amount,
        status=TransactionStatus.PENDING,
        reference=reference,
        session=session,
    )
    await session.commit()
    
    # Initialize Paystack transaction
    paystack = PaystackService()
    paystack_response = await paystack.initialize_transaction(
        email=auth_context.user.email,
        amount=payload.amount,
        reference=reference,
        meta={"wallet_id": str(wallet.id), "user_id": str(auth_context.user.id)},
    )
    
    return DepositResponse(
        reference=reference,
        authorization_url=paystack_response["data"]["authorization_url"],
        amount=payload.amount,
    )


@router.get("/deposit/{reference}/status", response_model=DepositStatusResponse)
async def deposit_status(
    request: Request,
    reference: str,
    session: AsyncSession = Depends(get_db),
    token: str = Depends(security),
    api_key: str = Depends(api_key_header),
):
    """
    Get the status of a deposit transaction.
    
    Note: This endpoint does NOT credit wallets. Only webhooks credit wallets.
    Requires authentication to prevent information disclosure.
    
    Args:
        reference: Paystack reference
        session: Database session
    
    Returns:
        DepositStatusResponse with status and amount
    """
    # Authenticate user
    auth_context = await get_authenticated_user(request)
    
    # Get transaction
    status_info = await get_deposit_status(reference, session)
    
    # Get transaction to verify ownership
    transaction = await get_transaction_by_reference(reference, session)
    
    # Verify transaction belongs to authenticated user
    if transaction.user_id != auth_context.user.id:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this transaction"
        )
    
    return DepositStatusResponse(
        reference=status_info["reference"],
        status=status_info["status"],
        amount=status_info["amount"],
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    request: Request,
    session: AsyncSession = Depends(get_db),
    token: str = Depends(security),
    api_key: str = Depends(api_key_header),
):
    """
    Get wallet balance.
    
    Auth: JWT or API key with "read" permission
    
    Args:
        session: Database session
    
    Returns:
        BalanceResponse with balance
    """
    # Check permission if API key
    if request.headers.get("x-api-key"):
        auth_context = await get_authenticated_user(request, required_permission="read")
    else:
        auth_context = await get_authenticated_user(request)
    
    # Get wallet
    wallet = await get_or_create_wallet(auth_context.user, session)
    await session.refresh(wallet)
    
    return BalanceResponse(
        wallet_number=wallet.wallet_number,
        balance=wallet.balance,
    )


@router.post("/transfer", response_model=TransferResponse)
@limiter.limit("20/minute")  # Max 20 transfers per minute per IP
async def transfer(
    request: Request,
    payload: TransferRequest,
    session: AsyncSession = Depends(get_db),
    token: str = Depends(security),
    api_key: str = Depends(api_key_header),
):
    """
    Transfer funds to another wallet.
    
    Auth: JWT or API key with "transfer" permission
    
    Args:
        payload: TransferRequest with wallet_number and amount
        session: Database session
    
    Returns:
        TransferResponse with status and transaction_id
    """
    # Check permission if API key
    if request.headers.get("x-api-key"):
        auth_context = await get_authenticated_user(request, required_permission="transfer")
    else:
        auth_context = await get_authenticated_user(request)
    
    # Perform transfer (atomic)
    transaction = await transfer_funds(
        sender_user=auth_context.user,
        recipient_wallet_number=payload.wallet_number,
        amount=payload.amount,
        session=session,
    )
    await session.commit()
    
    return TransferResponse(
        status="success",
        message="Transfer completed",
        transaction_id=transaction.id,
    )


@router.get("/transactions", response_model=TransactionHistoryResponse)
async def get_transactions(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    token: str = Depends(security),
    api_key: str = Depends(api_key_header),
):
    """
    Get transaction history for the user.
    
    Auth: JWT or API key with "read" permission
    
    Args:
        limit: Number of transactions to return (max 100)
        offset: Number of transactions to skip
        session: Database session
    
    Returns:
        TransactionHistoryResponse with list of transactions
    """
    # Check permission if API key
    if request.headers.get("x-api-key"):
        auth_context = await get_authenticated_user(request, required_permission="read")
    else:
        auth_context = await get_authenticated_user(request)
    
    transactions, total_count = await get_transaction_history(
        user_id=auth_context.user.id,
        session=session,
        limit=limit,
        offset=offset,
    )
    
    return TransactionHistoryResponse(
        transactions=transactions,
        count=total_count,
    )
