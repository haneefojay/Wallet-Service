from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.config.database import Base
from datetime import datetime
import uuid


class PaystackWebhookLog(Base):
    __tablename__ = "paystack_webhook_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event = Column(String(50), nullable=False, index=True)
    reference = Column(String(255), index=True, nullable=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, index=True)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("ix_webhook_reference_processed", "reference", "processed"),
    )
