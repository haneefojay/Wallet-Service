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
    update_transaction_status,
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
    body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    
    if not signature:
        logger.warning("Missing Paystack signature header")
        return {"status": False, "message": "Missing signature"}
        
    try:
        verify_paystack_webhook(body, signature)
    except Exception as e:
        logger.warning(f"Signature verification failed: {e}")
        return {"status": False, "message": "Invalid signature"}
    
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in webhook body")
        return {"status": False, "message": "Invalid JSON"}
    
    event = payload.get("event")
    data = payload.get("data", {})
    reference = data.get("reference")
    status_from_paystack = data.get("status")
    amount = data.get("amount", 0)  # In kobo
    
    async with async_session() as session:
        webhook_log = await get_or_create_webhook_log(
            event=event,
            reference=reference,
            payload=data,
            session=session,
        )
        
        if webhook_log.processed:
            await session.commit()
            return {"status": True}
        
        if event == "charge.success" and status_from_paystack == "success":
            try:
                transaction = await get_transaction_by_reference(reference, session)
                
                if not transaction:
                    logger.error(f"Transaction not found for reference: {reference}")
                    return {"status": True}
                
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
                
                await credit_wallet(transaction.id, session)
                
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
                logger.error(f"Webhook processing failed (success): {e}", exc_info=True)
                webhook_log.processed = False
                await session.rollback()

        elif event == "charge.failed":
            try:
                transaction = await get_transaction_by_reference(reference, session)
                if transaction:
                    await update_transaction_status(transaction.id, TransactionStatus.FAILED, session)
                    webhook_log.transaction_id = transaction.id
                    logger.info(f"Transaction failed: {reference}")
                
                webhook_log.processed = True

            except Exception as e:
                logger.error(f"Webhook processing failed (failed): {e}", exc_info=True)
                # We still mark as processed so we don't retry a failure notification endlessly if it's just a DB issue
                # But typically we might want to retry. For now, let's allow retry if it crashes.
                webhook_log.processed = False
                await session.rollback()

        elif event == "charge.pending":
            # Just log it or update status to PENDING (if it wasn't already)
            # Useful if a transaction was stuck in some other state or for logging visibility
            try:
                transaction = await get_transaction_by_reference(reference, session)
                if transaction:
                    # Optional: explicit update to PENDING if logic allows going back or confirming
                    # Usually it starts as PENDING.
                    await update_transaction_status(transaction.id, TransactionStatus.PENDING, session)
                    webhook_log.transaction_id = transaction.id
                    logger.info(f"Transaction pending: {reference}")
                
                webhook_log.processed = True
                
            except Exception as e:
                logger.error(f"Webhook processing failed (pending): {e}", exc_info=True)
                webhook_log.processed = False
                await session.rollback()

        else:
            # Mark as processed even if not an event we care about deeply, so we don't ignore it forever if sent
            webhook_log.processed = True
        
        await session.commit()
    
    return {"status": True}
