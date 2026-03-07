"""FastAPI endpoints for bio service."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .service import BioService

router = APIRouter(prefix="/api/v1/customers/{customer_ref}/bio")


# Request/Response models
class GenerateBioRequest(BaseModel):
    regenerate: bool = False


class UpdateBioRequest(BaseModel):
    bio: str


class BioResponse(BaseModel):
    exists: bool
    bio: str | None = None
    conversation_starters: list[str] = []
    generated_at: str | None = None
    generated_by: str | None = None
    edited_at: str | None = None
    edited_by: str | None = None
    is_staff_edited: bool = False
    is_stale: bool = False


class StalenessResponse(BaseModel):
    exists: bool
    is_stale: bool
    reason: str | None = None


# Dependency injection stubs - implement based on your framework
async def get_tenant_id() -> str:
    """Get tenant ID from request context (e.g., JWT, header)."""
    # TODO: Implement based on your auth system
    raise NotImplementedError("Implement get_tenant_id based on your auth system")


async def get_current_user_id() -> str:
    """Get current user ID from request context."""
    # TODO: Implement based on your auth system
    raise NotImplementedError("Implement get_current_user_id based on your auth system")


async def get_bio_service() -> BioService:
    """Get configured BioService instance."""
    # TODO: Implement dependency injection
    raise NotImplementedError("Implement get_bio_service dependency injection")


@router.get("", response_model=BioResponse)
async def get_bio(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Get current bio for customer."""
    bio = await bio_service.get_bio(tenant_id, customer_ref)
    if not bio:
        return BioResponse(exists=False)
    return BioResponse(exists=True, **bio)


@router.post("/generate", response_model=BioResponse)
async def generate_bio(
    customer_ref: str,
    request: GenerateBioRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Generate AI bio for customer."""
    try:
        bio = await bio_service.generate_bio(tenant_id, customer_ref, user_id)
        return BioResponse(exists=True, **bio)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("", response_model=BioResponse)
async def update_bio(
    customer_ref: str,
    request: UpdateBioRequest,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Staff updates bio (disables AI regeneration)."""
    bio = await bio_service.update_bio(
        tenant_id, customer_ref, request.bio, user_id
    )
    return BioResponse(exists=True, **bio)


@router.post("/reset", response_model=BioResponse)
async def reset_to_ai(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Clear staff edits and regenerate AI bio."""
    bio = await bio_service.reset_to_ai(tenant_id, customer_ref, user_id)
    return BioResponse(exists=True, **bio)


@router.get("/staleness", response_model=StalenessResponse)
async def check_staleness(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Check if cached bio is stale."""
    result = await bio_service.check_staleness(tenant_id, customer_ref)
    return StalenessResponse(**result)
