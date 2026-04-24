"""Tests for DynamoDB repositories with mocked clients."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.bios.repositories import (
    DynamoBioCacheRepository,
    DynamoRetailerSettingsRepository,
    DynamoAuditLogRepository,
    AuditAction,
)


class TestDynamoBioCacheRepository:
    """Tests for bio cache repository."""

    @patch("src.bios.repositories.boto3")
    def test_init_creates_table_resource(self, mock_boto3):
        """Initializes DynamoDB table resource."""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        repo = DynamoBioCacheRepository(
            table_name="test-table",
            region="us-west-2",
        )

        mock_boto3.resource.assert_called_once_with("dynamodb", region_name="us-west-2")
        mock_dynamodb.Table.assert_called_once_with("test-table")

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_returns_item(self, mock_boto3):
        """Returns cached bio when found."""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "tenant_id": "retailer-1",
                "customer_ref": "CUST001",
                "bio": "Customer bio text",
                "generated_at": "2024-01-15T10:00:00",
                "is_staff_edited": False,
            }
        }
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoBioCacheRepository(table_name="test-table")
        result = await repo.get("retailer-1", "CUST001")

        mock_table.get_item.assert_called_once_with(
            Key={"tenant_id": "retailer-1", "customer_ref": "CUST001"}
        )
        assert result["bio"] == "Customer bio text"
        assert result["is_staff_edited"] is False

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, mock_boto3):
        """Returns None when bio not in cache."""
        mock_table = Mock()
        mock_table.get_item.return_value = {}  # No "Item" key
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoBioCacheRepository(table_name="test-table")
        result = await repo.get("retailer-1", "CUST999")

        assert result is None

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_save_puts_item(self, mock_boto3):
        """Saves bio record to DynamoDB."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoBioCacheRepository(table_name="test-table")

        bio_record = {
            "tenant_id": "retailer-1",
            "customer_ref": "CUST001",
            "bio": "New bio text",
            "generated_at": "2024-01-15T10:00:00",
            "snapshot_hash": "abc123",
            "is_staff_edited": False,
        }

        await repo.save(bio_record)

        mock_table.put_item.assert_called_once_with(Item=bio_record)

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_delete_removes_item(self, mock_boto3):
        """Deletes bio from cache."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoBioCacheRepository(table_name="test-table")
        await repo.delete("retailer-1", "CUST001")

        mock_table.delete_item.assert_called_once_with(
            Key={"tenant_id": "retailer-1", "customer_ref": "CUST001"}
        )


class TestDynamoRetailerSettingsRepository:
    """Tests for retailer settings repository."""

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_bio_settings_returns_merged_settings(self, mock_boto3):
        """Returns retailer settings merged with defaults."""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "tenant_id": "retailer-1",
                "bio_settings": {
                    "tone": "luxury",
                    "include_spend_data": False,
                },
            }
        }
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoRetailerSettingsRepository(table_name="test-settings")
        result = await repo.get_bio_settings("retailer-1")

        # Custom settings
        assert result["tone"] == "luxury"
        assert result["include_spend_data"] is False
        # Defaults filled in
        assert result["include_conversation_starters"] is True
        assert result["max_notes_to_include"] == 10
        assert result["language"] == "en-AU"

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_bio_settings_returns_defaults_when_not_found(self, mock_boto3):
        """Returns default settings when retailer not configured."""
        mock_table = Mock()
        mock_table.get_item.return_value = {}  # No item
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoRetailerSettingsRepository(table_name="test-settings")
        result = await repo.get_bio_settings("new-retailer")

        assert result["tone"] == "professional"
        assert result["include_spend_data"] is True
        assert result["include_conversation_starters"] is True

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_bio_settings_handles_empty_bio_settings(self, mock_boto3):
        """Returns defaults when bio_settings key is missing."""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "tenant_id": "retailer-1",
                # No bio_settings key
            }
        }
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoRetailerSettingsRepository(table_name="test-settings")
        result = await repo.get_bio_settings("retailer-1")

        assert result["tone"] == "professional"


class TestDynamoAuditLogRepository:
    """Tests for audit log repository."""

    @patch("src.bios.repositories.boto3")
    @patch("src.bios.repositories.uuid")
    @pytest.mark.asyncio
    async def test_log_creates_audit_entry(self, mock_uuid, mock_boto3):
        """Logs audit event with correct structure."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table
        mock_uuid.uuid4.return_value = Mock(__str__=lambda x: "12345678-abcd")

        repo = DynamoAuditLogRepository(table_name="test-audit")

        await repo.log(
            tenant_id="retailer-1",
            customer_ref="CUST001",
            action=AuditAction.GENERATE,
            user_id="staff123",
            details={"bio_length": 500},
        )

        # Verify put_item was called
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["tenant_id"] == "retailer-1"
        assert item["customer_ref"] == "CUST001"
        assert item["action"] == "generate"
        assert item["user_id"] == "staff123"
        assert item["details"] == {"bio_length": 500}
        assert "CUST001#" in item["sort_key"]
        assert "timestamp" in item

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_log_without_details(self, mock_boto3):
        """Logs audit event without optional details."""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoAuditLogRepository(table_name="test-audit")

        await repo.log(
            tenant_id="retailer-1",
            customer_ref="CUST001",
            action=AuditAction.VIEW,
            user_id="staff123",
        )

        call_args = mock_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert "details" not in item

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_history_queries_by_customer(self, mock_boto3):
        """Queries audit history for specific customer."""
        mock_table = Mock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "tenant_id": "retailer-1",
                    "sort_key": "CUST001#2024-01-15T10:00:00#abc",
                    "action": "generate",
                    "user_id": "staff123",
                },
                {
                    "tenant_id": "retailer-1",
                    "sort_key": "CUST001#2024-01-14T09:00:00#def",
                    "action": "view",
                    "user_id": "staff456",
                },
            ]
        }
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoAuditLogRepository(table_name="test-audit")
        result = await repo.get_history("retailer-1", "CUST001", limit=10)

        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args.kwargs

        assert call_kwargs["KeyConditionExpression"] == "tenant_id = :tid AND begins_with(sort_key, :prefix)"
        assert call_kwargs["ExpressionAttributeValues"][":tid"] == "retailer-1"
        assert call_kwargs["ExpressionAttributeValues"][":prefix"] == "CUST001#"
        assert call_kwargs["ScanIndexForward"] is False  # Newest first
        assert call_kwargs["Limit"] == 10

        assert len(result) == 2
        assert result[0]["action"] == "generate"

    @patch("src.bios.repositories.boto3")
    @pytest.mark.asyncio
    async def test_get_history_returns_empty_list(self, mock_boto3):
        """Returns empty list when no history exists."""
        mock_table = Mock()
        mock_table.query.return_value = {"Items": []}
        mock_boto3.resource.return_value.Table.return_value = mock_table

        repo = DynamoAuditLogRepository(table_name="test-audit")
        result = await repo.get_history("retailer-1", "CUST999")

        assert result == []


class TestAuditActions:
    """Tests for audit action constants."""

    def test_action_constants(self):
        """Verifies audit action constant values."""
        assert AuditAction.VIEW == "view"
        assert AuditAction.GENERATE == "generate"
        assert AuditAction.EDIT == "edit"
        assert AuditAction.RESET == "reset"
