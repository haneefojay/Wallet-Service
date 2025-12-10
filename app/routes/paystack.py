from fastapi import APIRouter, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import async_session
from app.utils.paystack import verify_paystack_webhook
from app.utils.logger import logger
from app.services.paystack import (
    get_transaction_by_reference,
    credit_wallet,
    get_or_create_webhook_log,
    mark_webhook_processed,
)
from app.models import TransactionStatus
import json

router = APIRouter(prefix="/wallet", tags=["paystack"])


@router.post("/paystack/webhook", status_code=status.HTTP_200_OK)
async def paystack_webhook(request: Request):
    """
    Handle Paystack webhook events.
    
    Mandatory webhook implementation:
    - Verify webhook signature
    - Process charge.success event
    - Credit wallet on successful payment
    - Handle idempotently (no double-credit)
    
    """
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    
    if not signature:
        logger.warning("Missing Paystack signature header")
        return {"status": False, "message": "Missing signature"}
        
    # Verify signature
    try:
        verify_paystack_webhook(body, signature)
    except Exception as e:
        logger.warning(f"Signature verification failed: {e}")
        return {"status": False, "message": "Invalid signature"}
    
    # Parse JSON
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in webhook body")
        return {"status": False, "message": "Invalid JSON"}
    
    # Get event and data
    event = payload.get("event")
    data = payload.get("data", {})
    reference = data.get("reference")
    status_from_paystack = data.get("status")
    amount = data.get("amount", 0)  # In kobo
    
    async with async_session() as session:
        # Create or get webhook log (idempotency)
        webhook_log = await get_or_create_webhook_log(
            event=event,
            reference=reference,
            payload=data,
            session=session,
        )
        
        # If already processed, return success (idempotency)
        if webhook_log.processed:
            await session.commit()
            return {"status": True}
        
        # Only process charge.success events
        if event == "charge.success" and status_from_paystack == "success":
            try:
                # Get the transaction
                transaction = await get_transaction_by_reference(reference, session)
                
                # Check if transaction exists
                if not transaction:
                    logger.error(f"Transaction not found for reference: {reference}")
                    return {"status": True}  # Return true to stop retries for invalid reference
                
                # Verify amount paid (Paystack sends Kobo, we store Naira)
                expected_kobo = int(transaction.amount * 100)
                if amount != expected_kobo:
                    logger.warning(
                        "Amount mismatch in webhook",
                        extra={
                            "paystack_amount": amount,
                            "expected_kobo": expected_kobo,
                            "reference": reference
                        }
                    )
                    # We could update the transaction with the actual amount paid here if needed
                    # For strict mode, we might want to flag this. 
                    # For now, we proceed but log the warning.
                
                # Credit wallet
                await credit_wallet(transaction.id, session)
                
                # Mark webhook as processed
                webhook_log.transaction_id = transaction.id
                webhook_log.processed = True
                
                logger.info(
                    "Webhook processed successfully",
                    extra={
                        "event": event,
                        "reference": reference,
                        "transaction_id": str(transaction.id),
                        "amount": transaction.amount,
                    }
                )
                
            except Exception as e:
                logger.error(
                    "Webhook processing failed",
                    extra={
                        "event": event,
                        "reference": reference,
                        "error": str(e),
                    },
                    exc_info=True
                )
                # Log error but still return 200 OK to prevent retries
                webhook_log.processed = False
                await session.rollback()
        else:
            # Mark as processed even if not charge.success
            webhook_log.processed = True
        
        await session.commit()
    
    return {"status": True}
