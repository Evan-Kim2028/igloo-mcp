# Installation & Editor Setup

This guide covers installing igloo‑mcp, creating a Snowflake profile, and wiring popular MCP clients (Cursor, Codex/other, Claude Code).

## 1) Install igloo‑mcp

Recommended (PyPI):
```bash
uv pip install igloo-mcp
```

From source (contributors):
```bash
git clone https://github.com/Evan-Kim2028/igloo-mcp
cd igloo-mcp
uv sync
```

## 2) Create a Snowflake profile

igloo‑mcp uses Snowflake CLI profiles. Create one with SSO (external browser):
```bash
snow connection add \
  --connection-name my-profile \
  --account <account>.<region> \
  --user <username> \
  --warehouse COMPUTE_WH \
  --authenticator externalbrowser
```

Verify:
```bash
snow connection list
snow sql -q "SELECT CURRENT_VERSION()" --connection my-profile
```

More auth options (password, key‑pair) in docs/getting-started.md.

## 3) Configure your MCP client

All MCP clients provide a JSON configuration pointing to the server command. Use the same block below and place it in your client’s config file.

### Cursor
Config file: `~/.cursor/mcp.json`
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```

### Claude Code
Settings snippet:
```json
{
  "mcp": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```

### Codex / Other MCP clients
Most MCP clients accept a similar block under a client‑specific config file (path varies). Use:
```json
{
  "mcpServers": {
    "igloo-mcp": {
      "command": "igloo-mcp",
      "args": ["--profile", "my-profile"],
      "env": {"SNOWFLAKE_PROFILE": "my-profile"}
    }
  }
}
```
Refer to your client’s documentation for the exact config location.

## 4) Test

Server help:
```bash
igloo-mcp --profile my-profile --help
```

Optional connectivity check from your assistant: run `test_connection` or `execute_query` with `SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE()`.

## Troubleshooting

- Profile not found → `snow connection list` and use exact name.
- Server not discovered → restart the client after editing config; verify `which igloo-mcp`.
- Permission errors → confirm warehouse/database/schema access with your Snowflake admin.

## See Also

- [Getting Started Guide](getting-started.md) - Quick start overview
- [Configuration Guide](configuration.md) - Advanced configuration options
- [Authentication Guide](authentication.md) - Detailed authentication setup
- [MCP Integration Guide](mcp-integration.md) - MCP client configuration
- [Cursor MCP Setup](mcp/cursor-mcp-setup.md) - Cursor-specific setup
