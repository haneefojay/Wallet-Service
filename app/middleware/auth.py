from fastapi import Request
from typing import Optional, Tuple
from app.config.database import async_session
from app.services.auth import get_auth_user
from app.models import User


class AuthContext:
    """Context object for authenticated requests."""
    
    def __init__(self, user: User, user_id: str, auth_type: str, token: Optional[str] = None, api_key: Optional[str] = None):
        self.user = user
        self.user_id = user_id
        self.auth_type = auth_type  # "jwt" or "api_key"
        self.token = token
        self.api_key = api_key


async def extract_auth_header(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract JWT token or API key from request headers.
    
    Returns:
        Tuple of (jwt_token, api_key)
    """
    jwt_token = None
    api_key = None
    
    # Try to get JWT from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        jwt_token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Try to get API key from x-api-key header
    api_key = request.headers.get("x-api-key")
    
    return jwt_token, api_key


async def get_authenticated_user(
    request: Request,
    required_permission: Optional[str] = None,
) -> AuthContext:
    """
    Authenticate user from JWT or API key.
    
    Args:
        request: FastAPI Request
        required_permission: Optional permission required for API key
    
    Returns:
        AuthContext with user information
    
    Raises:
        Various authentication exceptions
    """
    jwt_token, api_key = await extract_auth_header(request)
    
    async with async_session() as session:
        user, user_id = await get_auth_user(
            token=jwt_token,
            api_key=api_key,
            session=session,
            required_permission=required_permission,
        )
        
        auth_type = "jwt" if jwt_token else "api_key"
        
        return AuthContext(
            user=user,
            user_id=user_id,
            auth_type=auth_type,
            token=jwt_token,
            api_key=api_key,
        )
