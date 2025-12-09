from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.database import get_db
from app.config.settings import settings
from app.models import User
from app.schemas import AuthToken
from app.utils.security import create_jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
from datetime import datetime
import os

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth configuration
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]


def get_oauth_flow():
    """Create and configure OAuth flow."""
    # Check if Google OAuth is configured
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
        )
    
    # Allow HTTP for development (remove in production)
    if settings.ENVIRONMENT == "development":
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )
    return flow


@router.get("/google")
async def google_login():
    """
    Redirect to Google OAuth consent screen.
    
    Returns:
        Authorization URL and state for OAuth flow
    """
    try:
        flow = get_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        return {
            "authorization_url": authorization_url,
            "state": state,
            "message": "Redirect user to authorization_url"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize OAuth flow: {str(e)}"
        )


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    
    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
        session: Database session
    
    Returns:
        AuthToken with JWT
    """
    try:
        # Exchange code for tokens
        flow = get_oauth_flow()
        flow.fetch_token(code=code)
        
        # Get user info from ID token
        credentials = flow.credentials
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        
        # Extract user information
        google_id = id_info['sub']
        email = id_info['email']
        name = id_info.get('name', email.split('@')[0])
        
        # Check if user exists
        result = await session.execute(
            select(User).where(User.google_id == google_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user
            user = User(
                google_id=google_id,
                email=email,
                name=name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        # Generate JWT
        token = create_jwt(str(user.id), user.email)
        
        return AuthToken(
            access_token=token,
            token_type="bearer",
            expires_in=24 * 3600,  # 24 hours in seconds
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}"
        )
