from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, APIKey
from app.utils.security import verify_api_key, verify_jwt
from app.utils.exceptions import (
    InvalidAPIKeyException,
    MissingPermissionException,
    InvalidJWTException,
    UserNotFoundException,
)
from datetime import datetime
from typing import Optional, Tuple


async def verify_jwt_token(token: str, session: AsyncSession) -> Tuple[User, str]:
    """
    Verify JWT token and return user.
    
    Args:
        token: JWT token string (without "Bearer " prefix)
        session: AsyncSession for database
    
    Returns:
        Tuple of (User object, user_id)
    
    Raises:
        InvalidJWTException
        UserNotFoundException
    """
    payload = verify_jwt(token)
    user_id = payload.get("sub")
    
    if not user_id:
        raise InvalidJWTException("Invalid JWT token structure")
    
    # Fetch user from database
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFoundException()
    
    return user, user_id


async def verify_api_key_auth(
    api_key: str,
    session: AsyncSession,
    required_permission: Optional[str] = None,
) -> Tuple[User, str]:
    """
    Verify API key and return user.
    
    Args:
        api_key: API key string
        session: AsyncSession for database
        required_permission: Optional permission to check (e.g., "deposit")
    
    Returns:
        Tuple of (User object, user_id)
    
    Raises:
        InvalidAPIKeyException
        MissingPermissionException
        UserNotFoundException
    """
    # Search for API key in database (need to check all hashes)
    result = await session.execute(
        select(APIKey).where(
            APIKey.is_active == True,
            APIKey.is_revoked == False,
        )
    )
    api_keys = result.scalars().all()
    
    found_key = None
    for stored_key in api_keys:
        if verify_api_key(api_key, stored_key.key_hash):
            found_key = stored_key
            break
    
    if not found_key:
        raise InvalidAPIKeyException("Invalid API key")
    
    # Check expiry
    if found_key.expires_at < datetime.utcnow():
        raise InvalidAPIKeyException("API key has expired")
    
    # Check permission if required
    if required_permission:
        if required_permission not in found_key.permissions:
            raise MissingPermissionException(required_permission)
    
    # Fetch user
    result = await session.execute(select(User).where(User.id == found_key.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFoundException()
    
    return user, str(found_key.user_id)


async def get_auth_user(
    token: Optional[str] = None,
    api_key: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    required_permission: Optional[str] = None,
) -> Tuple[User, str]:
    """
    Get authenticated user from JWT or API key.
    
    Args:
        token: JWT token (without "Bearer " prefix)
        api_key: API key string
        session: AsyncSession for database
        required_permission: Optional permission to check
    
    Returns:
        Tuple of (User object, user_id)
    
    Raises:
        InvalidJWTException or InvalidAPIKeyException
    """
    if token:
        return await verify_jwt_token(token, session)
    elif api_key:
        return await verify_api_key_auth(api_key, session, required_permission)
    else:
        raise InvalidJWTException("Missing JWT token or API key")
