"""Repository interfaces for bio caching and settings."""

from abc import ABC, abstractmethod
from typing import Optional

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
