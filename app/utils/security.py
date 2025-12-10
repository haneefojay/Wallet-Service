import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.utils.exceptions import InvalidJWTException


def hash_api_key(key: str) -> str:
    """Hash an API key using bcrypt."""
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    return bcrypt.checkpw(key.encode(), key_hash.encode())


def generate_api_key() -> str:
    """Generate a new API key."""
    random_part = secrets.token_urlsafe(32)
    return f"wsk_{random_part}"  # wsk = wallet service key


def create_jwt(user_id: str, email: str, expires_in_hours: int = None) -> str:
    """Create a JWT token for a user."""
    if expires_in_hours is None:
        expires_in_hours = settings.JWT_EXPIRY_HOURS
    
    expire = datetime.utcnow() + timedelta(hours=expires_in_hours)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def verify_jwt(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidJWTException("JWT token has expired")
    except jwt.InvalidTokenError:
        raise InvalidJWTException("Invalid JWT token")


def parse_expiry(expiry_str: str) -> datetime:
    """
    Convert expiry string (1H, 1D, 1M, 1Y) to datetime.
    
    Args:
        expiry_str: Format like "1H", "1D", "1M", "1Y"
    
    Returns:
        datetime object representing expiry time
    
    Raises:
        InvalidExpiryFormatException
    """
    from app.utils.exceptions import InvalidExpiryFormatException
    
    if not expiry_str or len(expiry_str) < 2:
        raise InvalidExpiryFormatException()
    
    number_str = expiry_str[:-1]
    unit = expiry_str[-1].upper()
    
    try:
        number = int(number_str)
    except ValueError:
        raise InvalidExpiryFormatException()
    
    now = datetime.utcnow()
    
    if unit == 'H':
        return now + timedelta(hours=number)
    elif unit == 'D':
        return now + timedelta(days=number)
    elif unit == 'M':
        return now + timedelta(days=number * 30)
    elif unit == 'Y':
        return now + timedelta(days=number * 365)
    else:
        raise InvalidExpiryFormatException()
