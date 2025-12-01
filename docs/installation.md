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

#### Global Setup (Recommended)

Use the Claude Code CLI to add igloo-mcp globally across all projects:

```bash
# Install as global MCP server
claude mcp add --scope user --transport stdio igloo-mcp -- uv tool run igloo_mcp --profile my-profile

# Verify installation
claude mcp list
```

Restart Claude Code and test:
- "Test my Snowflake connection"
- "Build a catalog for my database"

#### Project Setup (Team Sharing)

For team collaboration, create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "igloo-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["tool", "run", "igloo_mcp", "--profile", "my-profile"],
      "env": {
        "SNOWFLAKE_PROFILE": "my-profile"
      }
    }
  }
}
```

Commit `.mcp.json` to version control so your team automatically gets the same setup.

#### Manual Configuration

Alternatively, add to `~/.claude.json` under the `mcpServers` section:

```json
{
  "mcpServers": {
    "igloo-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["tool", "run", "igloo_mcp", "--profile", "my-profile"],
      "env": {
        "SNOWFLAKE_PROFILE": "my-profile"
      }
    }
  }
}
```

**Important Notes:**
- ✅ Executable is `igloo_mcp` (underscore), not `igloo-mcp` (dash)
- ✅ `type: "stdio"` is required for local MCP servers
- ✅ Global config: `~/.claude.json`, NOT `~/.config/claude-code/mcp.json`

See [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp) for more details.

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
