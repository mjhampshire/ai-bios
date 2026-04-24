"""Repository interfaces for bio caching, settings, and audit logging."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import uuid

import boto3


class BioCacheRepository(ABC):
    """Abstract interface for bio caching."""

    @abstractmethod
    async def get(self, tenant_id: str, customer_ref: str) -> Optional[dict]:
        """Get cached bio."""
        pass

    @abstractmethod
    async def save(self, bio_record: dict) -> None:
        """Save bio to cache."""
        pass

    @abstractmethod
    async def delete(self, tenant_id: str, customer_ref: str) -> None:
        """Delete cached bio."""
        pass


class RetailerSettingsRepository(ABC):
    """Abstract interface for retailer settings."""

    @abstractmethod
    async def get_bio_settings(self, tenant_id: str) -> dict:
        """Get bio generation settings for a tenant."""
        pass


class DynamoBioCacheRepository(BioCacheRepository):
    """DynamoDB implementation of bio cache."""

    def __init__(self, table_name: str, region: str = "ap-southeast-2"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    async def get(self, tenant_id: str, customer_ref: str) -> Optional[dict]:
        response = self.table.get_item(
            Key={"tenant_id": tenant_id, "customer_ref": customer_ref}
        )
        return response.get("Item")

    async def save(self, bio_record: dict) -> None:
        self.table.put_item(Item=bio_record)

    async def delete(self, tenant_id: str, customer_ref: str) -> None:
        self.table.delete_item(
            Key={"tenant_id": tenant_id, "customer_ref": customer_ref}
        )


class DynamoRetailerSettingsRepository(RetailerSettingsRepository):
    """DynamoDB implementation of retailer settings."""

    DEFAULT_SETTINGS = {
        "tone": "professional",
        "include_spend_data": True,
        "include_conversation_starters": True,
        "max_notes_to_include": 10,
        "language": "en-AU",
    }

    def __init__(self, table_name: str, region: str = "ap-southeast-2"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    async def get_bio_settings(self, tenant_id: str) -> dict:
        response = self.table.get_item(Key={"tenant_id": tenant_id})
        item = response.get("Item", {})
        settings = item.get("bio_settings", {})

        # Merge with defaults
        return {**self.DEFAULT_SETTINGS, **settings}


class AuditAction:
    """Audit log action types."""
    VIEW = "view"
    GENERATE = "generate"
    EDIT = "edit"
    RESET = "reset"


class AuditLogRepository(ABC):
    """Abstract interface for audit logging."""

    @abstractmethod
    async def log(
        self,
        tenant_id: str,
        customer_ref: str,
        action: str,
        user_id: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log an audit event."""
        pass

    @abstractmethod
    async def get_history(
        self,
        tenant_id: str,
        customer_ref: str,
        limit: int = 50,
    ) -> list[dict]:
        """Get audit history for a customer's bio."""
        pass


class DynamoAuditLogRepository(AuditLogRepository):
    """DynamoDB implementation of audit logging.

    Table schema:
        Partition Key: tenant_id (String)
        Sort Key: sort_key (String) - format: "{customer_ref}#{timestamp}#{uuid}"

    This allows querying all audit entries for a tenant, filtered by customer_ref prefix.
    """

    def __init__(self, table_name: str, region: str = "ap-southeast-2"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    async def log(
        self,
        tenant_id: str,
        customer_ref: str,
        action: str,
        user_id: str,
        details: Optional[dict] = None,
    ) -> None:
        """Log an audit event."""
        timestamp = datetime.utcnow().isoformat()
        event_id = str(uuid.uuid4())[:8]

        # Sort key enables range queries by customer and time
        sort_key = f"{customer_ref}#{timestamp}#{event_id}"

        item = {
            "tenant_id": tenant_id,
            "sort_key": sort_key,
            "customer_ref": customer_ref,
            "action": action,
            "user_id": user_id,
            "timestamp": timestamp,
        }

        if details:
            item["details"] = details

        self.table.put_item(Item=item)

    async def get_history(
        self,
        tenant_id: str,
        customer_ref: str,
        limit: int = 50,
    ) -> list[dict]:
        """Get audit history for a customer's bio, newest first."""
        response = self.table.query(
            KeyConditionExpression="tenant_id = :tid AND begins_with(sort_key, :prefix)",
            ExpressionAttributeValues={
                ":tid": tenant_id,
                ":prefix": f"{customer_ref}#",
            },
            ScanIndexForward=False,  # Newest first
            Limit=limit,
        )

        return response.get("Items", [])
