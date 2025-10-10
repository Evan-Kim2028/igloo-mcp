"""Unified configuration and session management for igloo-mcp."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Mapping, MutableMapping, Optional

import yaml  # type: ignore[import-untyped]


class ConfigError(RuntimeError):
    """Raised when configuration sources cannot be parsed or merged."""


@dataclass(frozen=True)
class SnowflakeConfig:
    profile: str
    warehouse: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    role: Optional[str] = None

    def apply_overrides(
        self, overrides: Mapping[str, Optional[str]]
    ) -> "SnowflakeConfig":
        if not overrides:
            return self
        data = asdict(self)
        for key, value in overrides.items():
            if key in data:
                data[key] = value
        return SnowflakeConfig(**data)

    def session_defaults(self) -> Dict[str, Optional[str]]:
        return {
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "role": self.role,
        }


@dataclass(frozen=True)
class SQLPermissions:
    """SQL statement permissions configuration."""

    select: bool = True
    show: bool = True
    describe: bool = True
    use: bool = True
    insert: bool = True
    update: bool = True
    create: bool = True
    alter: bool = True
    delete: bool = False  # Blocked by default - use soft delete
    drop: bool = False  # Blocked by default - use rename
    truncate: bool = False  # Blocked by default - use DELETE with WHERE
    unknown: bool = False  # Reject unparseable SQL by default

    def get_allow_list(self) -> list[str]:
        """Get list of allowed SQL statement types.

        Returns lowercase statement types to match upstream validation.
        """
        allowed = []
        for stmt_type, is_allowed in [
            ("select", self.select),
            ("show", self.show),
            ("describe", self.describe),
            ("use", self.use),
            ("insert", self.insert),
            ("update", self.update),
            ("create", self.create),
            ("alter", self.alter),
            ("delete", self.delete),
            ("drop", self.drop),
            ("truncate", self.truncate),
            ("unknown", self.unknown),
        ]:
            if is_allowed:
                allowed.append(stmt_type)
        return allowed

    def get_disallow_list(self) -> list[str]:
        """Get list of disallowed SQL statement types.

        Returns lowercase statement types to match upstream validation.
        """
        disallowed = []
        for stmt_type, is_allowed in [
            ("select", self.select),
            ("show", self.show),
            ("describe", self.describe),
            ("use", self.use),
            ("insert", self.insert),
            ("update", self.update),
            ("create", self.create),
            ("alter", self.alter),
            ("delete", self.delete),
            ("drop", self.drop),
            ("truncate", self.truncate),
            ("unknown", self.unknown),
        ]:
            if not is_allowed:
                disallowed.append(stmt_type)
        return disallowed


@dataclass(frozen=True)
class Config:
    snowflake: SnowflakeConfig
    max_concurrent_queries: int = 5
    connection_pool_size: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout_seconds: int = 300
    log_level: str = "INFO"
    sql_permissions: SQLPermissions = field(default_factory=SQLPermissions)

    def apply_overrides(self, overrides: "ConfigOverrides") -> "Config":
        if overrides.is_empty():
            return self
        cfg = self
        if overrides.snowflake:
            cfg = replace(
                cfg, snowflake=cfg.snowflake.apply_overrides(overrides.snowflake)
            )
        for key, value in overrides.values.items():
            if value is not None:
                cfg = replace(cfg, **{key: value})
        return cfg

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        loader = ConfigLoader()
        env_map = dict(env or os.environ)
        base = loader._default_config(env_map)
        overrides = loader._overrides_from_env(env_map)
        if overrides.is_empty():
            return base
        return base.apply_overrides(overrides)

    @classmethod
    def from_yaml(
        cls,
        config_path: str,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "Config":
        loader = ConfigLoader()
        env_map = dict(env or os.environ)
        base = loader._default_config(env_map)
        cfg = base.apply_overrides(loader._overrides_from_file(Path(config_path)))
        env_overrides = loader._overrides_from_env(env_map)
        if env_overrides.is_empty():
            return cfg
        return cfg.apply_overrides(env_overrides)

    def save_to_yaml(self, config_path: str) -> None:
        payload = {
            "snowflake": {
                "profile": self.snowflake.profile,
                "warehouse": self.snowflake.warehouse,
                "database": self.snowflake.database,
                "schema": self.snowflake.schema,
                "role": self.snowflake.role,
            },
            "max_concurrent_queries": self.max_concurrent_queries,
            "connection_pool_size": self.connection_pool_size,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "timeout_seconds": self.timeout_seconds,
            "log_level": self.log_level,
        }
        with open(config_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, default_flow_style=False, sort_keys=False)


@dataclass(frozen=True)
class ConfigOverrides:
    snowflake: Dict[str, Optional[str]] = field(default_factory=dict)
    values: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.snowflake and not self.values


class ConfigLoader:
    _ENV_SNOWFLAKE_KEYS: Dict[str, str] = {
        "SNOWFLAKE_PROFILE": "profile",
        "SNOWFLAKE_WAREHOUSE": "warehouse",
        "SNOWFLAKE_DATABASE": "database",
        "SNOWFLAKE_SCHEMA": "schema",
        "SNOWFLAKE_ROLE": "role",
    }

    _ENV_RUNTIME_KEYS: Dict[str, tuple[str, type]] = {
        "MAX_CONCURRENT_QUERIES": ("max_concurrent_queries", int),
        "CONNECTION_POOL_SIZE": ("connection_pool_size", int),
        "RETRY_ATTEMPTS": ("retry_attempts", int),
        "RETRY_DELAY": ("retry_delay", float),
        "TIMEOUT_SECONDS": ("timeout_seconds", int),
        "LOG_LEVEL": ("log_level", str),
    }

    _RUNTIME_CASTERS: Dict[str, type] = {
        "max_concurrent_queries": int,
        "connection_pool_size": int,
        "retry_attempts": int,
        "retry_delay": float,
        "timeout_seconds": int,
        "log_level": str,
    }

    def __init__(self, *, default_profile: str = "default") -> None:
        self._default_profile = default_profile

    def build(
        self,
        *,
        config_path: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        cli_overrides: Mapping[str, Optional[str]] | None = None,
    ) -> Config:
        env_map = dict(env or os.environ)
        config = self._default_config(env_map)

        if config_path:
            config = config.apply_overrides(
                self._overrides_from_file(Path(config_path))
            )

        env_overrides = self._overrides_from_env(env_map)
        if not env_overrides.is_empty():
            config = config.apply_overrides(env_overrides)

        if cli_overrides:
            cli_overrides_obj = self._overrides_from_cli(cli_overrides)
            if not cli_overrides_obj.is_empty():
                config = config.apply_overrides(cli_overrides_obj)

        return config

    def _default_config(self, env: Mapping[str, str]) -> Config:
        profile = env.get("SNOWCLI_DEFAULT_PROFILE") or self._default_profile
        return Config(snowflake=SnowflakeConfig(profile=profile))

    def _overrides_from_env(self, env: Mapping[str, str]) -> ConfigOverrides:
        snowflake: Dict[str, Optional[str]] = {}
        for env_key, attr in self._ENV_SNOWFLAKE_KEYS.items():
            if env_key in env and env[env_key] != "":
                snowflake[attr] = env[env_key]

        runtime: Dict[str, Any] = {}
        for env_key, (field_name, caster) in self._ENV_RUNTIME_KEYS.items():
            if env_key not in env or env[env_key] == "":
                continue
            raw_value = env[env_key]
            try:
                runtime[field_name] = caster(raw_value)
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    f"Invalid value for {env_key}: {raw_value!r}"
                ) from exc

        return ConfigOverrides(snowflake=snowflake, values=runtime)

    def _overrides_from_file(self, path: Path) -> ConfigOverrides:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - yaml errors rare
            raise ConfigError(f"Failed to parse configuration file {path}") from exc

        if not isinstance(data, MutableMapping):
            raise ConfigError("Configuration file must contain a mapping at the root")

        snowflake_data = data.get("snowflake", {})
        if snowflake_data and not isinstance(snowflake_data, MutableMapping):
            raise ConfigError("The 'snowflake' section must be a mapping")

        snowflake: Dict[str, Optional[str]] = {}
        if isinstance(snowflake_data, Mapping):
            for key in ("profile", "warehouse", "database", "schema", "role"):
                if key in snowflake_data:
                    snowflake[key] = snowflake_data.get(key)

        runtime_candidates = {
            key: data[key] for key in self._RUNTIME_CASTERS.keys() if key in data
        }
        runtime = self.normalize_runtime_values(
            runtime_candidates, source=f"file {path}"
        )

        return ConfigOverrides(snowflake=snowflake, values=runtime)

    def _overrides_from_cli(
        self, overrides: Mapping[str, Optional[str]]
    ) -> ConfigOverrides:
        snowflake: Dict[str, Optional[str]] = {}
        runtime_candidates: Dict[str, Any] = {}

        for key, value in overrides.items():
            if value is None:
                continue
            if key in ("profile", "warehouse", "database", "schema", "role"):
                snowflake[key] = value
            elif key in self._RUNTIME_CASTERS:
                runtime_candidates[key] = value

        runtime = self.normalize_runtime_values(
            runtime_candidates, source="CLI overrides"
        )
        return ConfigOverrides(snowflake=snowflake, values=runtime)

    def normalize_runtime_values(
        self,
        values: Mapping[str, Any],
        *,
        source: str,
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for field_name, caster in self._RUNTIME_CASTERS.items():
            if field_name not in values:
                continue
            raw = values[field_name]
            try:
                normalized[field_name] = caster(raw)
            except (TypeError, ValueError) as exc:
                raise ConfigError(
                    f"Invalid value for {field_name} from {source}: {raw!r}"
                ) from exc
        return normalized


class ConfigManager:
    def __init__(self, loader: ConfigLoader | None = None) -> None:
        self._loader = loader or ConfigLoader()
        self._lock = RLock()
        self._config: Config | None = None

    def get(self) -> Config:
        with self._lock:
            if self._config is None:
                self._config = self._loader.build()
            return self._config

    def set(self, config: Config) -> None:
        if not isinstance(config, Config):
            raise TypeError("config must be an instance of Config")
        with self._lock:
            self._config = config

    def load(
        self,
        *,
        config_path: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        cli_overrides: Mapping[str, Optional[str]] | None = None,
    ) -> Config:
        config = self._loader.build(
            config_path=config_path,
            env=env,
            cli_overrides=cli_overrides,
        )
        with self._lock:
            self._config = config
        return config

    def apply_overrides(self, overrides: ConfigOverrides) -> Config:
        with self._lock:
            current = self._config or self._loader.build()
            updated = current.apply_overrides(overrides)
            self._config = updated
            return updated

    def normalize_runtime_values(
        self, values: Mapping[str, Any], *, source: str
    ) -> Dict[str, Any]:
        return self._loader.normalize_runtime_values(values, source=source)


_CONFIG_MANAGER = ConfigManager()


def get_config() -> Config:
    return _CONFIG_MANAGER.get()


def set_config(config: Config) -> None:
    _CONFIG_MANAGER.set(config)


def load_config(
    *,
    config_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, Optional[str]] | None = None,
) -> Config:
    return _CONFIG_MANAGER.load(
        config_path=config_path,
        env=env,
        cli_overrides=cli_overrides,
    )


def apply_config_overrides(
    *,
    snowflake: Mapping[str, Optional[str]] | None = None,
    values: Mapping[str, Any] | None = None,
) -> Config:
    overrides = ConfigOverrides(
        snowflake=dict(snowflake or {}),
        values=_CONFIG_MANAGER.normalize_runtime_values(
            dict(values or {}),
            source="runtime overrides",
        ),
    )
    return _CONFIG_MANAGER.apply_overrides(overrides)
