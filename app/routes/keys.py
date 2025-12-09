from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.middleware.auth import get_authenticated_user

# Security scheme
security = HTTPBearer()
from app.services.wallet import (
    create_api_key,
    rollover_api_key,
    list_api_keys,
    revoke_api_key,
)
from app.schemas import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    RolloverAPIKeyRequest,
    RolloverAPIKeyResponse,
    APIKeyListResponse,
)

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.post("/create", response_model=CreateAPIKeyResponse, dependencies=[Depends(security)])
async def create_key(
    request: Request,
    payload: CreateAPIKeyRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.
    
    Args:
        payload: CreateAPIKeyRequest with name, permissions, and expiry
        session: Database session
    
    Returns:
        CreateAPIKeyResponse with the new API key (shown only once)
    """
    auth_context = await get_authenticated_user(request)
    
    api_key_string, api_key_obj = await create_api_key(
        user_id=auth_context.user.id,
        name=payload.name,
        permissions=payload.permissions,
        expiry_str=payload.expiry,
        session=session,
    )
    
    await session.commit()
    
    return CreateAPIKeyResponse(
        api_key=api_key_string,
        expires_at=api_key_obj.expires_at,
        key_id=api_key_obj.id,
    )


@router.post("/rollover", response_model=RolloverAPIKeyResponse, dependencies=[Depends(security)])
async def rollover_key(
    request: Request,
    payload: RolloverAPIKeyRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Rollover an expired API key.
    
    Args:
        payload: RolloverAPIKeyRequest with expired_key_id and new expiry
        session: Database session
    
    Returns:
        RolloverAPIKeyResponse with the new API key
    """
    auth_context = await get_authenticated_user(request)
    
    api_key_string, api_key_obj = await rollover_api_key(
        user_id=auth_context.user.id,
        expired_key_id=payload.expired_key_id,
        new_expiry_str=payload.expiry,
        session=session,
    )
    
    await session.commit()
    
    return RolloverAPIKeyResponse(
        api_key=api_key_string,
        expires_at=api_key_obj.expires_at,
    )


@router.get("/list", response_model=APIKeyListResponse, dependencies=[Depends(security)])
async def list_keys(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    List all API keys for the user.
    
    Args:
        session: Database session
    
    Returns:
        APIKeyListResponse with list of keys
    """
    auth_context = await get_authenticated_user(request)
    
    keys = await list_api_keys(
        user_id=auth_context.user.id,
        session=session,
    )
    
    return APIKeyListResponse(
        keys=keys,
        count=len(keys),
    )


@router.post("/revoke/{key_id}", dependencies=[Depends(security)])
async def revoke_key(
    request: Request,
    key_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Revoke an API key.
    
    Args:
        key_id: ID of the key to revoke
        session: Database session
    
    Returns:
        Success message
    """
    auth_context = await get_authenticated_user(request)
    
    await revoke_api_key(
        user_id=auth_context.user.id,
        key_id=key_id,
        session=session,
    )
    
    await session.commit()
    
    return {"status": "success", "message": "API key revoked"}
