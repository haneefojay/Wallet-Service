from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.config.database import Base
from datetime import datetime
import uuid


class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    wallet_number = Column(String(20), unique=True, index=True, nullable=False)
    balance = Column(Float, default=0.0)
    currency = Column(String(3), default="NGN")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet", foreign_keys="Transaction.wallet_id", cascade="all, delete-orphan")
