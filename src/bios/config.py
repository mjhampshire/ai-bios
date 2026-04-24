"""Configuration management for the bio service."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClickHouseConfig:
    """ClickHouse connection configuration."""
    host: str
    port: int
    username: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "ClickHouseConfig":
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "default"),
        )

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
        }


@dataclass
class DynamoDBConfig:
    """DynamoDB configuration."""
    region: str
    bio_cache_table: str
    retailer_settings_table: str
    audit_log_table: str

    @classmethod
    def from_env(cls) -> "DynamoDBConfig":
        return cls(
            region=os.getenv("AWS_REGION", "ap-southeast-2"),
            bio_cache_table=os.getenv("BIO_CACHE_TABLE", "twc-customer-bios"),
            retailer_settings_table=os.getenv("RETAILER_SETTINGS_TABLE", "twc-retailer-settings"),
            audit_log_table=os.getenv("AUDIT_LOG_TABLE", "twc-bio-audit-log"),
        )


@dataclass
class AnthropicConfig:
    """Anthropic API configuration."""
    api_key: str
    timeout: float
    model: str
    max_tokens: int

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return cls(
            api_key=api_key,
            timeout=float(os.getenv("ANTHROPIC_TIMEOUT", "30.0")),
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024")),
        )


def get_clickhouse_config() -> ClickHouseConfig:
    """Get ClickHouse configuration from environment."""
    return ClickHouseConfig.from_env()


def get_dynamodb_config() -> DynamoDBConfig:
    """Get DynamoDB configuration from environment."""
    return DynamoDBConfig.from_env()


def get_anthropic_config() -> AnthropicConfig:
    """Get Anthropic configuration from environment."""
    return AnthropicConfig.from_env()
