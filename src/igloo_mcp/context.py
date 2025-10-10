"""Service context helpers for Igloo MCP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Config, get_config, load_config
from .mcp_health import MCPHealthMonitor
from .mcp_resources import MCPResourceManager


@dataclass(slots=True)
class ServiceContext:
    """Aggregates shared services for CLI and MCP surfaces."""

    config: Config
    health_monitor: MCPHealthMonitor
    resource_manager: MCPResourceManager


def create_service_context(
    *,
    profile: Optional[str] = None,
    config_path: Optional[str] = None,
    existing_config: Optional[Config] = None,
) -> ServiceContext:
    """Factory for service contexts.

    If ``existing_config`` is provided it takes precedence over other parameters.
    Otherwise the current global config is reused unless ``profile`` or ``config_path``
    overrides are supplied.
    """

    if existing_config is not None:
        config = existing_config
    else:
        overrides = {}
        if profile:
            overrides["profile"] = profile
        if config_path or overrides:
            config = load_config(
                config_path=config_path,
                cli_overrides=overrides or None,
            )
        else:
            config = get_config()

    health_monitor = MCPHealthMonitor()
    resource_manager = MCPResourceManager(health_monitor=health_monitor)
    return ServiceContext(
        config=config,
        health_monitor=health_monitor,
        resource_manager=resource_manager,
    )
