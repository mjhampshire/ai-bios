"""Bio service orchestrator."""

import hashlib
import json
from datetime import datetime
from typing import Optional

from .aggregator import BioDataAggregator
from .generator import BioGenerator
from .repositories import (
    BioCacheRepository,
    RetailerSettingsRepository,
    AuditLogRepository,
    AuditAction,
)


class BioService:
    """Orchestrates bio generation and caching."""

    def __init__(
        self,
        aggregator: BioDataAggregator,
        generator: BioGenerator,
        cache: BioCacheRepository,
        settings: RetailerSettingsRepository,
        audit_log: Optional[AuditLogRepository] = None,
    ):
        self.aggregator = aggregator
        self.generator = generator
        self.cache = cache
        self.settings = settings
        self.audit_log = audit_log

    async def _log_audit(
        self,
        tenant_id: str,
        customer_ref: str,
        action: str,
        user_id: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log an audit event if audit logging is enabled."""
        if self.audit_log:
            try:
                await self.audit_log.log(
                    tenant_id=tenant_id,
                    customer_ref=customer_ref,
                    action=action,
                    user_id=user_id,
                    details=details,
                )
            except Exception:
                # Don't fail the main operation if audit logging fails
                pass

    async def get_bio(
        self,
        tenant_id: str,
        customer_ref: str,
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Get cached bio if exists."""
        bio = await self.cache.get(tenant_id, customer_ref)

        # Log view action if user_id provided
        if bio and user_id:
            await self._log_audit(
                tenant_id=tenant_id,
                customer_ref=customer_ref,
                action=AuditAction.VIEW,
                user_id=user_id,
            )

        return bio

    async def generate_bio(
        self, tenant_id: str, customer_ref: str, user_id: str
    ) -> dict:
        """
        Generate a new bio for a customer.

        1. Check if staff-edited bio exists (block regeneration)
        2. Aggregate customer data from ClickHouse
        3. Get retailer settings (tone, etc.)
        4. Call Claude to generate bio
        5. Cache result
        """
        # Check for staff-edited bio
        existing = await self.cache.get(tenant_id, customer_ref)
        if existing and existing.get("is_staff_edited"):
            raise ValueError(
                "Cannot regenerate staff-edited bio. Use reset_to_ai first."
            )

        # Aggregate data
        customer_data = await self.aggregator.aggregate(tenant_id, customer_ref)

        if not customer_data.get("customer"):
            raise ValueError(f"Customer not found: {customer_ref}")

        # Get retailer settings
        retailer_settings = await self.settings.get_bio_settings(tenant_id)

        # Generate bio
        result = self.generator.generate(
            customer_data=customer_data,
            tone=retailer_settings.get("tone", "professional"),
            include_conversation_starters=retailer_settings.get(
                "include_conversation_starters", True
            ),
        )

        # Create snapshot hash for staleness detection
        snapshot_hash = self._create_snapshot_hash(customer_data)

        # Cache result
        bio_record = {
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "bio": result["bio"],
            "conversation_starters": result["conversation_starters"],
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": user_id,
            "snapshot_hash": snapshot_hash,
            "is_staff_edited": False,
            "is_stale": False,
        }

        await self.cache.save(bio_record)

        # Audit log
        await self._log_audit(
            tenant_id=tenant_id,
            customer_ref=customer_ref,
            action=AuditAction.GENERATE,
            user_id=user_id,
            details={
                "bio_length": len(result["bio"]),
                "conversation_starters_count": len(result["conversation_starters"]),
                "tone": retailer_settings.get("tone", "professional"),
            },
        )

        return bio_record

    async def update_bio(
        self, tenant_id: str, customer_ref: str, bio_text: str, user_id: str
    ) -> dict:
        """Staff edits and saves bio. Disables AI regeneration."""
        bio_record = {
            "tenant_id": tenant_id,
            "customer_ref": customer_ref,
            "bio": bio_text,
            "conversation_starters": [],  # Staff can add manually if needed
            "edited_at": datetime.utcnow().isoformat(),
            "edited_by": user_id,
            "is_staff_edited": True,
            "is_stale": False,
        }

        await self.cache.save(bio_record)

        # Audit log
        await self._log_audit(
            tenant_id=tenant_id,
            customer_ref=customer_ref,
            action=AuditAction.EDIT,
            user_id=user_id,
            details={"bio_length": len(bio_text)},
        )

        return bio_record

    async def reset_to_ai(
        self, tenant_id: str, customer_ref: str, user_id: str
    ) -> dict:
        """Clear staff edits and regenerate AI bio."""
        # Audit log the reset action
        await self._log_audit(
            tenant_id=tenant_id,
            customer_ref=customer_ref,
            action=AuditAction.RESET,
            user_id=user_id,
        )

        await self.cache.delete(tenant_id, customer_ref)
        # generate_bio will log its own GENERATE action
        return await self.generate_bio(tenant_id, customer_ref, user_id)

    async def check_staleness(self, tenant_id: str, customer_ref: str) -> dict:
        """Check if a cached bio is stale based on current data."""
        cached = await self.cache.get(tenant_id, customer_ref)
        if not cached:
            return {"exists": False, "is_stale": False}

        if cached.get("is_staff_edited"):
            # Staff-edited bios are never considered stale
            return {"exists": True, "is_stale": False, "reason": None}

        # Aggregate current data and compare hash
        current_data = await self.aggregator.aggregate(tenant_id, customer_ref)
        current_hash = self._create_snapshot_hash(current_data)

        is_stale = current_hash != cached.get("snapshot_hash")
        reason = None
        if is_stale:
            reason = self._get_stale_reason(cached, current_data)

        return {"exists": True, "is_stale": is_stale, "reason": reason}

    def _create_snapshot_hash(self, data: dict) -> str:
        """Create hash of key data points for staleness detection."""
        key_data = {
            "orders": data.get("purchase_summary", {}).get("total_orders"),
            "last_purchase": data.get("purchase_summary", {}).get("last_purchase_date"),
            "wishlist_count": data.get("wishlist", {}).get("count"),
            "notes_count": len(data.get("staff_notes", [])),
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _get_stale_reason(self, cached: dict, current_data: dict) -> str:
        """Generate a human-readable reason for staleness."""
        # Compare key metrics
        reasons = []

        cached_orders = 0  # Would need to store this in cache
        current_orders = current_data.get("purchase_summary", {}).get("total_orders", 0)
        if current_orders > cached_orders:
            reasons.append("New orders placed")

        current_wishlist = current_data.get("wishlist", {}).get("count", 0)
        if current_wishlist > 0:
            reasons.append("Wishlist updated")

        return reasons[0] if reasons else "New activity detected"
