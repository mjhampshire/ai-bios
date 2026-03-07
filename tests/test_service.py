"""Tests for BioService."""

import hashlib
import json

import pytest

from src.bios.service import BioService


class TestSnapshotHash:
    """Tests for snapshot hash generation."""

    def test_create_snapshot_hash(self):
        """Creates consistent hash from data."""
        service = BioService.__new__(BioService)

        data = {
            "purchase_summary": {
                "total_orders": 10,
                "last_purchase_date": "2025-03-01",
            },
            "wishlist": {"count": 5},
            "staff_notes": [],
        }

        hash1 = service._create_snapshot_hash(data)
        hash2 = service._create_snapshot_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length

    def test_different_data_different_hash(self):
        """Different data produces different hash."""
        service = BioService.__new__(BioService)

        data1 = {
            "purchase_summary": {"total_orders": 10, "last_purchase_date": "2025-03-01"},
            "wishlist": {"count": 5},
            "staff_notes": [],
        }

        data2 = {
            "purchase_summary": {"total_orders": 11, "last_purchase_date": "2025-03-01"},
            "wishlist": {"count": 5},
            "staff_notes": [],
        }

        hash1 = service._create_snapshot_hash(data1)
        hash2 = service._create_snapshot_hash(data2)

        assert hash1 != hash2

    def test_missing_fields_handled(self):
        """Handles missing fields gracefully."""
        service = BioService.__new__(BioService)

        data = {}  # Empty data

        hash_result = service._create_snapshot_hash(data)

        assert hash_result is not None
        assert len(hash_result) == 32
