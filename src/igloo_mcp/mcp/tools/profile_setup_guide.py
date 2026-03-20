"""Profile Setup Guide MCP Tool - Interactive guidance for first-time setup.

Provides step-by-step instructions for setting up Snowflake profiles,
tailored to the user's current configuration state.
"""

from __future__ import annotations

from typing import Any

from igloo_mcp import profile_utils
from igloo_mcp.config import Config
from igloo_mcp.mcp.compat import get_logger

from .base import MCPTool, ensure_request_id, tool_error_handler

logger = get_logger(__name__)


class ProfileSetupGuideTool(MCPTool):
    """MCP tool providing interactive profile setup guidance.

    Analyzes the current configuration state and provides tailored
    step-by-step instructions for setting up or fixing profiles.
    """

    def __init__(self, config: Config):
        self.config = config

    @property
    def name(self) -> str:
        return "profile_setup_guide"

    @property
    def description(self) -> str:
        return "Get setup guidance for Snowflake profiles, tailored to current config state."

    @property
    def category(self) -> str:
        return "profile"

    @property
    def tags(self) -> list[str]:
        return ["profile", "setup", "guide", "onboarding", "help"]

    @property
    def usage_examples(self) -> list[dict[str, Any]]:
        return [
            {
                "description": "Get setup guide for initial configuration",
                "parameters": {},
            },
            {
                "description": "Get help setting up SSO authentication",
                "parameters": {"topic": "sso"},
            },
        ]

    @tool_error_handler("profile_setup_guide")
    async def execute(
        self,
        topic: str | None = None,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate profile setup guidance.

        Args:
            topic: Optional focus topic (general, sso, keypair, multi_env, troubleshooting)
            request_id: Optional request correlation ID for tracing

        Returns:
            Setup guide with steps tailored to current configuration state
        """
        request_id = ensure_request_id(request_id)

        logger.info(
            "profile_setup_guide_started",
            extra={"topic": topic, "request_id": request_id},
        )

        config_path = profile_utils.get_snowflake_config_path()
        config_exists = config_path.exists()
        available_profiles = sorted(profile_utils.get_available_profiles())
        default_profile = profile_utils.get_default_profile()

        # Analyze current state
        state = self._analyze_state(config_exists, available_profiles, default_profile)

        # Generate appropriate guide based on state and topic
        guide = self._generate_guide(
            state=state,
            topic=topic or "general",
            config_path=str(config_path),
            available_profiles=available_profiles,
            default_profile=default_profile,
        )

        result = {
            "current_state": state,
            "guide": guide,
        }

        logger.info(
            "profile_setup_guide_completed",
            extra={"state": state["status"], "request_id": request_id},
        )

        return result

    def _analyze_state(
        self,
        config_exists: bool,
        available_profiles: list[str],
        default_profile: str | None,
    ) -> dict[str, Any]:
        """Analyze current configuration state."""
        if not config_exists:
            return {
                "status": "no_config",
                "message": "Snowflake configuration file not found",
                "needs_setup": True,
            }

        if not available_profiles:
            return {
                "status": "no_profiles",
                "message": "Config file exists but no profiles defined",
                "needs_setup": True,
            }

        if not default_profile:
            return {
                "status": "no_default",
                "message": f"Found {len(available_profiles)} profile(s) but no default set",
                "needs_setup": False,
                "needs_attention": True,
            }

        return {
            "status": "configured",
            "message": f"{len(available_profiles)} profile(s) available, default: {default_profile}",
            "needs_setup": False,
        }

    def _generate_guide(
        self,
        *,
        state: dict[str, Any],
        topic: str,
        config_path: str,
        available_profiles: list[str],
        default_profile: str | None,
    ) -> dict[str, Any]:
        """Generate setup guide based on state and topic."""
        guides: dict[str, dict[str, Any]] = {
            "general": self._general_guide(state, config_path, available_profiles, default_profile),
            "sso": self._sso_guide(config_path),
            "keypair": self._keypair_guide(config_path),
            "multi_env": self._multi_env_guide(config_path, available_profiles),
            "troubleshooting": self._troubleshooting_guide(state, config_path, available_profiles),
        }

        return guides.get(topic, guides["general"])

    def _general_guide(
        self,
        state: dict[str, Any],
        config_path: str,
        available_profiles: list[str],
        default_profile: str | None,
    ) -> dict[str, Any]:
        """General setup guide based on current state."""
        status = state["status"]

        if status == "no_config":
            return {
                "title": "Initial Snowflake Profile Setup",
                "steps": [
                    {
                        "step": 1,
                        "action": "Install Snowflake CLI",
                        "command": "pip install snowflake-cli",
                    },
                    {
                        "step": 2,
                        "action": "Create your first connection profile",
                        "command": (
                            'snow connection add --connection-name "default" '
                            '--account "<account>.<region>" '
                            '--user "<username>" '
                            "--authenticator externalbrowser"
                        ),
                    },
                    {
                        "step": 3,
                        "action": "Set as default profile",
                        "command": 'snow connection set-default "default"',
                    },
                    {
                        "step": 4,
                        "action": "Test the connection",
                        "command": "snow connection test --connection default",
                    },
                ],
                "config_path": config_path,
                "next": "Run list_profiles to verify, then test_connection to validate connectivity",
            }

        if status == "no_profiles":
            return {
                "title": "Add a Connection Profile",
                "message": f"Config file found at {config_path} but no profiles defined.",
                "steps": [
                    {
                        "step": 1,
                        "action": "Create a connection profile",
                        "command": (
                            'snow connection add --connection-name "default" '
                            '--account "<account>.<region>" '
                            '--user "<username>" '
                            "--authenticator externalbrowser"
                        ),
                    },
                    {
                        "step": 2,
                        "action": "Set as default",
                        "command": 'snow connection set-default "default"',
                    },
                ],
                "config_path": config_path,
            }

        if status == "no_default":
            return {
                "title": "Set a Default Profile",
                "message": f"Profiles available: {', '.join(available_profiles)}",
                "steps": [
                    {
                        "step": 1,
                        "action": f"Set default profile",
                        "command": f'snow connection set-default "{available_profiles[0]}"',
                    },
                ],
                "alternative": f'Or use: export SNOWFLAKE_PROFILE="{available_profiles[0]}"',
            }

        # Already configured
        return {
            "title": "Profile Configuration Summary",
            "message": "Your profiles are set up correctly.",
            "profiles": available_profiles,
            "default_profile": default_profile,
            "tips": [
                "Use list_profiles to see all profiles with details",
                "Use switch_profile to change the active profile mid-session",
                "Use health_check to validate the current connection",
            ],
            "available_topics": [
                "sso - Set up SSO/browser authentication",
                "keypair - Set up key-pair authentication for automation",
                "multi_env - Set up dev/staging/prod profiles",
                "troubleshooting - Diagnose profile issues",
            ],
        }

    def _sso_guide(self, config_path: str) -> dict[str, Any]:
        """Guide for setting up SSO/browser authentication."""
        return {
            "title": "SSO / Browser Authentication Setup",
            "steps": [
                {
                    "step": 1,
                    "action": "Create profile with externalbrowser authenticator",
                    "command": (
                        'snow connection add --connection-name "sso-profile" '
                        '--account "<account>.<region>" '
                        '--user "<your-email>" '
                        "--authenticator externalbrowser"
                    ),
                },
                {
                    "step": 2,
                    "action": "Test the connection (will open browser)",
                    "command": 'snow connection test --connection "sso-profile"',
                },
            ],
            "notes": [
                "externalbrowser opens your default browser for Okta/SSO login",
                "For Okta-specific URLs, use: --authenticator https://your-org.okta.com",
                "Browser auth requires a desktop environment (not headless servers)",
            ],
        }

    def _keypair_guide(self, config_path: str) -> dict[str, Any]:
        """Guide for setting up key-pair authentication."""
        return {
            "title": "Key-Pair Authentication Setup",
            "description": "Best for automation, CI/CD, and headless environments.",
            "steps": [
                {
                    "step": 1,
                    "action": "Generate RSA key pair",
                    "command": (
                        "openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt"
                    ),
                },
                {
                    "step": 2,
                    "action": "Extract public key",
                    "command": "openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub",
                },
                {
                    "step": 3,
                    "action": "Register public key with Snowflake",
                    "command": (
                        "-- Run in Snowflake:\n"
                        "ALTER USER <username> SET RSA_PUBLIC_KEY='<contents of rsa_key.pub>';"
                    ),
                },
                {
                    "step": 4,
                    "action": "Start igloo-mcp with keypair auth",
                    "command": (
                        "igloo_mcp --auth-mode keypair "
                        "--account <account> "
                        "--user <username> "
                        "--private-key-path ./rsa_key.p8"
                    ),
                },
            ],
            "notes": [
                "Store private keys securely - never commit to version control",
                "Key-pair auth bypasses Snowflake profile validation (uses direct connection)",
                "Ideal for CI/CD pipelines and automated workflows",
            ],
        }

    def _multi_env_guide(
        self, config_path: str, available_profiles: list[str]
    ) -> dict[str, Any]:
        """Guide for setting up multi-environment profiles."""
        return {
            "title": "Multi-Environment Profile Setup",
            "description": "Set up separate profiles for dev, staging, and production.",
            "current_profiles": available_profiles or ["(none)"],
            "steps": [
                {
                    "step": 1,
                    "action": "Create development profile",
                    "command": (
                        'snow connection add --connection-name "dev" '
                        '--account "<dev-account>" --user "<user>" '
                        '--warehouse "DEV_WH" --database "DEV_DB" '
                        "--authenticator externalbrowser"
                    ),
                },
                {
                    "step": 2,
                    "action": "Create staging profile",
                    "command": (
                        'snow connection add --connection-name "staging" '
                        '--account "<staging-account>" --user "<user>" '
                        '--warehouse "STAGING_WH" --database "STAGING_DB" '
                        "--authenticator externalbrowser"
                    ),
                },
                {
                    "step": 3,
                    "action": "Create production profile",
                    "command": (
                        'snow connection add --connection-name "prod" '
                        '--account "<prod-account>" --user "<user>" '
                        '--warehouse "PROD_WH" --database "PROD_DB" '
                        "--authenticator externalbrowser"
                    ),
                },
                {
                    "step": 4,
                    "action": "Set dev as default",
                    "command": 'snow connection set-default "dev"',
                },
            ],
            "switching": {
                "description": "Switch between environments using:",
                "options": [
                    'MCP tool: switch_profile(profile_name="staging")',
                    'Environment: export SNOWFLAKE_PROFILE="prod"',
                    'CLI flag: igloo_mcp --profile staging',
                ],
            },
        }

    def _troubleshooting_guide(
        self,
        state: dict[str, Any],
        config_path: str,
        available_profiles: list[str],
    ) -> dict[str, Any]:
        """Troubleshooting guide for common profile issues."""
        return {
            "title": "Profile Troubleshooting Guide",
            "current_state": state,
            "common_issues": [
                {
                    "issue": "Profile not found",
                    "diagnosis": "Run list_profiles to see available profiles",
                    "fix": 'snow connection add --connection-name "<name>" ...',
                },
                {
                    "issue": "Connection timeout",
                    "diagnosis": "Check account identifier and network access",
                    "fix": "Verify account format: <account>.<region> (e.g., xy12345.us-east-1)",
                },
                {
                    "issue": "Authentication failed",
                    "diagnosis": "Run health_check with include_profile=true",
                    "fix": "Check authenticator type and credentials in config.toml",
                },
                {
                    "issue": "Wrong warehouse/database/role",
                    "diagnosis": "Run test_connection to see current session context",
                    "fix": 'snow connection update "<profile>" --warehouse "<new-wh>"',
                },
                {
                    "issue": "SSO browser not opening",
                    "diagnosis": "Headless environment without display",
                    "fix": "Use key-pair auth instead: profile_setup_guide(topic='keypair')",
                },
            ],
            "diagnostic_tools": [
                "list_profiles - See all available profiles",
                "test_connection - Check connectivity",
                "health_check(response_mode='full') - Full diagnostics",
            ],
            "config_path": config_path,
        }

    def get_parameter_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "general, sso, keypair, multi_env, or troubleshooting",
                    "enum": ["general", "sso", "keypair", "multi_env", "troubleshooting"],
                },
            },
        }
