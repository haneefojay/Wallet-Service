from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.config.database import Base
from datetime import datetime
import uuid


class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, index=True, nullable=False)  # bcrypt hash
    name = Column(String(255), nullable=False)
    permissions = Column(JSON, default=[], nullable=False)  # ["deposit", "transfer", "read"]
    is_active = Column(Boolean, default=True, index=True)
    is_revoked = Column(Boolean, default=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index("ix_api_key_user_active", "user_id", "is_active"),
    )
