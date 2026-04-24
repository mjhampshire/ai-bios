"""Data aggregation service for customer bios."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import clickhouse_connect

logger = logging.getLogger(__name__)


class BioDataAggregator:
    """Aggregates customer data from ClickHouse for bio generation."""

    def __init__(self, clickhouse_config: dict):
        self.client = clickhouse_connect.get_client(
            host=clickhouse_config["host"],
            port=clickhouse_config["port"],
            username=clickhouse_config["username"],
            password=clickhouse_config["password"],
            database=clickhouse_config["database"],
        )
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def aggregate(self, tenant_id: str, customer_ref: str) -> dict:
        """
        Aggregate all customer data in parallel.
        Returns structured dict ready for prompt injection.

        Handles partial failures gracefully - if a query fails,
        that section returns empty/default data and aggregation continues.
        """
        loop = asyncio.get_event_loop()

        # Define queries with their result keys and default values
        queries = [
            ("customer", self._fetch_customer_profile, {}),
            ("preferences", self._fetch_preferences, {"likes": {}, "dislikes": {}, "sizes": {}}),
            ("purchase_summary", self._fetch_purchase_summary, {}),
            ("top_purchased", self._fetch_top_purchased, {"categories": [], "brands": [], "colors": []}),
            ("recent_purchases", self._fetch_recent_purchases, []),
            ("wishlist", self._fetch_wishlist, {"count": 0, "items": []}),
            ("recent_browsing", self._fetch_browsing, {"categories": [], "brands": []}),
            ("customer_messages", self._fetch_customer_messages, []),
            ("staff_notes", self._fetch_staff_notes, []),
        ]

        # Run all queries in parallel with error handling
        tasks = [
            loop.run_in_executor(
                self.executor,
                self._safe_fetch,
                key,
                fetch_func,
                default,
                tenant_id,
                customer_ref,
            )
            for key, fetch_func, default in queries
        ]

        results = await asyncio.gather(*tasks)

        # Combine results into dict
        return {key: value for key, value in results}

    def _safe_fetch(
        self,
        key: str,
        fetch_func: Callable,
        default: Any,
        tenant_id: str,
        customer_ref: str,
    ) -> tuple[str, Any]:
        """
        Execute a fetch function with error handling.
        Returns (key, result) tuple. On failure, returns (key, default).
        """
        try:
            result = fetch_func(tenant_id, customer_ref)
            return (key, result)
        except Exception as e:
            logger.warning(
                f"Failed to fetch {key} for {tenant_id}/{customer_ref}: {e}"
            )
            return (key, default)

    def _fetch_customer_profile(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT
                firstName, lastName, vipStatus, loyaltyTier,
                memberSince, preferredStore, usualStore
            FROM TWCCUSTOMER
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND deleted = '0'
            LIMIT 1
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        if result.row_count == 0:
            return {}

        row = result.first_row
        return {
            "name": f"{row[0]} {row[1]}".strip(),
            "first_name": row[0],
            "vip_status": row[2],
            "loyalty_tier": row[3],
            "member_since": row[4].strftime("%Y-%m") if row[4] else None,
            "preferred_store": row[5],
            "usual_store": row[6],
        }

    def _fetch_preferences(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT preferences
            FROM TWCPREFERENCES
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND deleted = '0'
            ORDER BY isPrimary DESC, updatedAt DESC
            LIMIT 1
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        if result.row_count == 0:
            return {"likes": {}, "dislikes": {}, "sizes": {}}

        prefs_json = result.first_row[0]
        return self._parse_preferences_json(prefs_json)

    def _parse_preferences_json(self, prefs_json: str) -> dict:
        """Parse the preferences JSON into likes/dislikes/sizes."""
        try:
            data = json.loads(prefs_json) if prefs_json else {}
        except json.JSONDecodeError:
            return {"likes": {}, "dislikes": {}, "sizes": {}}

        likes: dict[str, list[Any]] = {
            "categories": [],
            "colors": [],
            "brands": [],
            "fabrics": [],
        }
        dislikes: dict[str, list[Any]] = {
            "categories": [],
            "colors": [],
            "brands": [],
            "fabrics": [],
        }
        sizes: dict[str, Any] = {}

        # Categories
        for item in data.get("categories", []):
            target = dislikes if item.get("dislike") else likes
            target["categories"].append(item.get("value"))

        # Colors
        for item in data.get("colours", []):
            target = dislikes if item.get("dislike") else likes
            target["colors"].append(item.get("value"))

        # Sizes by category
        size_fields = ["dresses", "tops", "bottoms", "footwear"]
        for field in size_fields:
            items = data.get(field, [])
            if items:
                sizes[field] = items[0].get("value")

        return {"likes": likes, "dislikes": dislikes, "sizes": sizes}

    def _fetch_purchase_summary(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT
                count(DISTINCT orderId) as total_orders,
                sum(amount) as lifetime_spend,
                avg(amount) as avg_order_value,
                min(orderDate) as first_purchase,
                max(orderDate) as last_purchase,
                dateDiff('day', max(orderDate), now()) as days_since_last
            FROM TWCALLORDERS
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        row = result.first_row
        return {
            "total_orders": row[0] or 0,
            "lifetime_spend": float(row[1] or 0),
            "avg_order_value": round(float(row[2] or 0)),
            "first_purchase_date": row[3].strftime("%Y-%m-%d") if row[3] else None,
            "last_purchase_date": row[4].strftime("%Y-%m-%d") if row[4] else None,
            "days_since_last_purchase": row[5] or 0,
        }

    def _fetch_top_purchased(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT
                v.category, v.brand, v.color,
                count(*) as cnt, sum(ol.orderLineValue) as spend
            FROM ORDERLINE ol
            JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
            WHERE ol.tenantId = {tenant_id:String}
              AND ol.customerRef = {customer_ref:String}
            GROUP BY v.category, v.brand, v.color
            ORDER BY cnt DESC
            LIMIT 20
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        categories: dict[str, int] = {}
        brands: dict[str, int] = {}
        colors: dict[str, int] = {}
        for row in result.result_rows:
            cat, brand, color, cnt, spend = row
            if cat:
                categories[cat] = categories.get(cat, 0) + cnt
            if brand:
                brands[brand] = brands.get(brand, 0) + cnt
            if color:
                colors[color] = colors.get(color, 0) + cnt

        return {
            "categories": sorted(
                categories.keys(), key=lambda x: categories[x], reverse=True
            )[:5],
            "brands": sorted(brands.keys(), key=lambda x: brands[x], reverse=True)[:5],
            "colors": sorted(colors.keys(), key=lambda x: colors[x], reverse=True)[:5],
        }

    def _fetch_recent_purchases(self, tenant_id: str, customer_ref: str) -> list:
        result = self.client.query(
            """
            SELECT ol.orderLineDate, ol.variantName, ol.orderLineValue, v.brand, v.category
            FROM ORDERLINE ol
            JOIN TWCVARIANT v ON ol.variantRef = v.variantRef AND ol.tenantId = v.tenantId
            WHERE ol.tenantId = {tenant_id:String}
              AND ol.customerRef = {customer_ref:String}
              AND ol.orderLineDate >= now() - INTERVAL 6 MONTH
            ORDER BY ol.orderLineDate DESC
            LIMIT 5
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        return [
            {
                "date": row[0].strftime("%Y-%m-%d"),
                "item": row[1],
                "price": row[2],
                "brand": row[3],
            }
            for row in result.result_rows
        ]

    def _fetch_wishlist(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT wi.productName, wi.price, wi.customerInterest, wi.createdAt, wi.brandId
            FROM TWCWISHLIST w
            JOIN WISHLISTITEM wi ON w.wishlistId = wi.wishlistId AND w.tenantId = wi.tenantId
            WHERE w.tenantId = {tenant_id:String}
              AND w.customerRef = {customer_ref:String}
              AND w.deleted = '0' AND wi.deleted = '0' AND wi.purchased = '0'
            ORDER BY wi.createdAt DESC
            LIMIT 5
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        items = [
            {"name": row[0], "price": row[1], "interest": row[2], "brand": row[4]}
            for row in result.result_rows
        ]
        return {"count": len(items), "items": items}

    def _fetch_browsing(self, tenant_id: str, customer_ref: str) -> dict:
        result = self.client.query(
            """
            SELECT productType, brand, count(*) as cnt
            FROM TWCCLICKSTREAM
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND timeStamp >= now() - INTERVAL 30 DAY
            GROUP BY productType, brand
            ORDER BY cnt DESC
            LIMIT 10
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        categories: dict[str, int] = {}
        brands: dict[str, int] = {}
        for row in result.result_rows:
            if row[0]:
                categories[row[0]] = categories.get(row[0], 0) + row[2]
            if row[1]:
                brands[row[1]] = brands.get(row[1], 0) + row[2]

        return {
            "categories": sorted(
                categories.keys(), key=lambda x: categories[x], reverse=True
            )[:5],
            "brands": sorted(brands.keys(), key=lambda x: brands[x], reverse=True)[:5],
        }

    def _fetch_customer_messages(self, tenant_id: str, customer_ref: str) -> list:
        result = self.client.query(
            """
            SELECT message, createdAt, storeName
            FROM TWCCUSTOMER_MESSAGE
            WHERE tenantId = {tenant_id:String}
              AND customerRef = {customer_ref:String}
              AND isReply = '1'
            ORDER BY createdAt DESC
            LIMIT 5
        """,
            parameters={"tenant_id": tenant_id, "customer_ref": customer_ref},
        )

        return [
            {
                "message": self._truncate_message(row[0]),
                "date": row[1].strftime("%Y-%m-%d"),
                "store": row[2],
            }
            for row in result.result_rows
        ]

    def _truncate_message(self, message: str, max_length: int = 500) -> str:
        """Truncate message to max_length, adding ellipsis if truncated."""
        if not message or len(message) <= max_length:
            return message
        return message[:max_length - 3] + "..."

    def _fetch_staff_notes(self, tenant_id: str, customer_ref: str) -> list:
        # Placeholder - implement when TWCNOTES table is added
        return []
