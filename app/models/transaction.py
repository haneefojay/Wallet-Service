from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.config.database import Base
from datetime import datetime
import uuid
import enum


class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    TRANSFER = "transfer"
    WITHDRAWAL = "withdrawal"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True)
    type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING, index=True)
    reference = Column(String(255), unique=True, index=True, nullable=True)  # Paystack reference
    recipient_wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=True)  # For transfers
    description = Column(String(500), nullable=True)
    meta = Column(JSON, default={}, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="transactions", foreign_keys=[user_id])
    wallet = relationship("Wallet", back_populates="transactions", foreign_keys=[wallet_id])
    
    __table_args__ = (
        Index("ix_transaction_status_created", "status", "created_at"),
    )
