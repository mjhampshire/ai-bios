"""FastAPI endpoints for bio service."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from .aggregator import BioDataAggregator
from .config import get_clickhouse_config, get_dynamodb_config, get_anthropic_config
from .generator import BioGenerator, BioAPIError, BioParseError, BioGenerationError
from .repositories import (
    DynamoBioCacheRepository,
    DynamoRetailerSettingsRepository,
    DynamoAuditLogRepository,
)
from .service import BioService

router = APIRouter(prefix="/api/v1/customers/{customer_ref}/bio", tags=["bios"])


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


# Singleton instances (lazy initialized)
_bio_service: Optional[BioService] = None


def _get_bio_service_instance() -> BioService:
    """Get or create singleton BioService instance."""
    global _bio_service
    if _bio_service is None:
        ch_config = get_clickhouse_config()
        dynamo_config = get_dynamodb_config()
        anthropic_config = get_anthropic_config()

        aggregator = BioDataAggregator(ch_config.to_dict())
        generator = BioGenerator(
            api_key=anthropic_config.api_key,
            timeout=anthropic_config.timeout,
            model=anthropic_config.model,
            max_tokens=anthropic_config.max_tokens,
        )
        cache = DynamoBioCacheRepository(
            table_name=dynamo_config.bio_cache_table,
            region=dynamo_config.region,
        )
        settings = DynamoRetailerSettingsRepository(
            table_name=dynamo_config.retailer_settings_table,
            region=dynamo_config.region,
        )
        audit_log = DynamoAuditLogRepository(
            table_name=dynamo_config.audit_log_table,
            region=dynamo_config.region,
        )

        _bio_service = BioService(
            aggregator=aggregator,
            generator=generator,
            cache=cache,
            settings=settings,
            audit_log=audit_log,
        )
    return _bio_service


# Dependency injection
async def get_tenant_id(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", description="Retailer/tenant identifier")
) -> str:
    """Get tenant ID from X-Tenant-ID header."""
    return x_tenant_id


async def get_current_user_id(
    x_user_id: str = Header(..., alias="X-User-ID", description="Staff user identifier")
) -> str:
    """Get current user ID from X-User-ID header."""
    return x_user_id


async def get_bio_service() -> BioService:
    """Get configured BioService instance."""
    return _get_bio_service_instance()


@router.get("", response_model=BioResponse)
async def get_bio(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Get current bio for customer."""
    bio = await bio_service.get_bio(tenant_id, customer_ref, user_id=user_id)
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
    except BioAPIError as e:
        # Rate limits, auth errors, timeouts, connection errors
        status_code = 503 if e.retry_after else 502
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
        raise HTTPException(status_code=status_code, detail=str(e), headers=headers)
    except BioParseError as e:
        # Claude returned unparseable response
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {e}")


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
    try:
        bio = await bio_service.reset_to_ai(tenant_id, customer_ref, user_id)
        return BioResponse(exists=True, **bio)
    except BioAPIError as e:
        status_code = 503 if e.retry_after else 502
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
        raise HTTPException(status_code=status_code, detail=str(e), headers=headers)
    except BioParseError as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {e}")


@router.get("/staleness", response_model=StalenessResponse)
async def check_staleness(
    customer_ref: str,
    tenant_id: str = Depends(get_tenant_id),
    bio_service: BioService = Depends(get_bio_service),
):
    """Check if cached bio is stale."""
    result = await bio_service.check_staleness(tenant_id, customer_ref)
    return StalenessResponse(**result)
