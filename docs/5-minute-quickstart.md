# 5-Minute Quickstart

Get igloo-mcp running with your AI assistant in under 5 minutes!

**Who this is for**: Users new to Snowflake and MCP who want to get started quickly.

## Prerequisites Check (30 seconds)

```bash
# Check Python version (need 3.12+)
python --version

# Check if Snowflake CLI is installed
snow --version

# If not installed, install it:
pip install snowflake-cli-labs
```

**What you'll need**:
- Snowflake account with username/password (or ask your admin)
- AI assistant that supports MCP (Claude Code, Continue, Cline, Zed, etc.)
- Your Snowflake account identifier (looks like: `mycompany-prod.us-east-1`)

## Step 1: Install igloo-mcp (1 minute)

```bash
# Install from PyPI
uv pip install igloo-mcp

# Verify installation
python -c "import igloo_mcp; print('igloo-mcp installed successfully')"
# Expected: igloo-mcp installed successfully
```

> **Note**: igloo-mcp automatically installs `snowflake-cli-labs` as a dependency

## Step 2: Create Snowflake Profile (2 minutes)

```bash
# Create a profile with password authentication (easiest for getting started)
snow connection add \
  --connection-name "quickstart" \
  --account "<your-account>.<region>" \
  --user "<your-username>" \
  --password \
  --warehouse "<your-warehouse>"

# Enter password when prompted
# Expected: "Connection 'quickstart' added successfully"
```

**Finding your account identifier**:
- Your Snowflake URL: `https://abc12345.us-east-1.snowflakecomputing.com`
- Your account identifier: `abc12345.us-east-1` (remove `.snowflakecomputing.com`)

**Finding your warehouse**:
- Trial accounts: Usually `COMPUTE_WH` (default warehouse)
- Enterprise: Check Snowflake UI → Admin → Warehouses, or ask your admin
- Common names: `COMPUTE_WH`, `WH_DEV`, `ANALYTICS_WH`

**Don't have these?** Ask your Snowflake admin for:
- Account identifier
- Username & password
- Warehouse name

## Step 3: Configure Your AI Assistant (1 minute)

Add this to your AI assistant's MCP configuration:

### Claude Code
Edit `~/.config/claude-code/mcp.json`:

```json
{
  "mcpServers": {
    "snowflake": {
      "command": "nanuk-mcp",
      "args": ["--profile", "quickstart"]
    }
  }
}
```

### Cline (VS Code)
Edit `~/.continue/config.json`:

```json
{
  "mcpServers": {
    "snowflake": {
      "command": "nanuk-mcp",
      "args": ["--profile", "quickstart"]
    }
  }
}
```

### Zed Editor
Add via Settings → MCP Servers:
- **Command**: `igloo-mcp`
- **Args**: `["--profile", "quickstart"]`

**Restart your AI assistant** after configuring.

## Step 4: Test Your Setup (30 seconds)

### Verify Snowflake Connection
```bash
# Test your profile
snow sql -q "SELECT CURRENT_VERSION()" --connection quickstart
```

### Verify MCP Server
```bash
# Start MCP server (should show help without errors)
igloo-mcp --profile quickstart --help
```

## Step 5: Test It! (30 seconds)

In your AI assistant, try these prompts:

```
"Test my Snowflake connection"
```

Expected: ✅ Connection successful message

```
"Show me my Snowflake databases"
```

Expected: List of your databases

```
"What tables are in my database?"
```

Expected: List of tables (if you have access)

## Success! 🎉

You've successfully:
- ✅ Installed igloo-mcp
- ✅ Configured Snowflake connection
- ✅ Connected your AI assistant
- ✅ Ran your first Snowflake queries via AI

**Time taken**: ~5 minutes

## What's Next?

### Explore MCP Tools

Try these prompts in your AI assistant:

```
"Build a catalog for MY_DATABASE"
→ Explores all tables, columns, and metadata

"Show me lineage for USERS table"
→ Visualizes data dependencies

"Profile the CUSTOMERS table"
→ Gets statistics and data quality info

"Execute: SELECT COUNT(*) FROM orders WHERE created_at > CURRENT_DATE - 7"
→ Runs custom SQL queries
```

### Improve Security

Replace password auth with key-pair authentication:

1. **Generate keys**:
```bash
mkdir -p ~/.snowflake
openssl genrsa -out ~/.snowflake/key.pem 2048
openssl rsa -in ~/.snowflake/key.pem -pubout -out ~/.snowflake/key.pub
chmod 400 ~/.snowflake/key.pem
```

2. **Upload public key to Snowflake**:
```bash
# Format key for Snowflake
cat ~/.snowflake/key.pub | grep -v "BEGIN\|END" | tr -d '\n'

# In Snowflake, run:
ALTER USER <your_username> SET RSA_PUBLIC_KEY='<paste_key_here>';
```

3. **Update your profile**:
```bash
snow connection add \
  --connection-name "quickstart" \
  --account "mycompany-prod.us-east-1" \
  --user "your-username" \
  --private-key-file "~/.snowflake/key.pem" \
  --warehouse "COMPUTE_WH"
```

### Learn More

- 📖 [Getting Started Guide](getting-started.md) - Detailed setup and concepts
- 🔧 [MCP Integration Guide](mcp/mcp_server_user_guide.md) - Advanced MCP configuration
- 🛠️ [API Reference](api/README.md) - All available MCP tools
- 🐛 [Troubleshooting](profile_troubleshooting_guide.md) - Common issues and solutions

## Troubleshooting

### "Profile not found"
**Fix**:
```bash
# List profiles
snow connection list

# Use exact name from list in your MCP config
```

### "Connection failed"
**Fix**:
- Verify account format: `org-account.region` (not `https://...`)
- Check username/password are correct
- Ensure warehouse exists and you have access
- Try: `snow sql -q "SELECT 1" --connection quickstart`

### "MCP tools not showing up"
**Fix**:
1. Verify igloo-mcp is installed: `which igloo-mcp`
2. Check MCP config JSON syntax is valid
3. **Restart your AI assistant completely**
4. Check AI assistant logs for errors

### "Permission denied"
**Fix**:
- Ensure you have `USAGE` on warehouse
- Check database/schema access: `SHOW GRANTS TO USER <your_username>`
- Contact your Snowflake admin for permissions

### Still stuck?

- 💬 [GitHub Discussions](https://github.com/Evan-Kim2028/igloo-mcp/discussions) - Community help
- 🐛 [GitHub Issues](https://github.com/Evan-Kim2028/igloo-mcp/issues) - Report bugs
- 📖 [Full Documentation](getting-started.md) - Comprehensive guides

---

**🐻‍❄️ igloo-mcp v0.1.0 - MCP-Only Architecture**

*For users migrating from CLI tools: See [Migration Guide](migration-guide.md)*
