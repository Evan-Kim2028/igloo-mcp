# Error Catalog

This document provides a comprehensive catalog of errors that can occur when using Igloo MCP, along with solutions and troubleshooting steps.

## Common Error Types

### Authentication Errors

#### JWT Token Invalid
**Error**: `JWT token invalid`
**Cause**: Public key not properly uploaded to Snowflake or key mismatch
**Solution**:
1. Verify public key was uploaded correctly to Snowflake
2. Check key permissions (`chmod 400`)
3. Regenerate key pair if needed

#### Account Not Found
**Error**: `Account not found`
**Cause**: Incorrect account identifier format
**Solution**:
- Use format: `<org>-<account>.<region>`
- Example: `myorg-myaccount.us-east-1`
- Check account name in Snowflake console

#### User Not Found
**Error**: `User not found`
**Cause**: Incorrect username or user doesn't exist
**Solution**:
- Verify username spelling
- Check user exists in Snowflake
- Ensure user has proper permissions

### Connection Errors

#### Connection Timeout
**Error**: `Connection timeout`
**Cause**: Network issues or Snowflake service unavailable
**Solution**:
- Check network connectivity
- Verify Snowflake service status
- Increase timeout settings if needed

#### Warehouse Not Found
**Error**: `Warehouse not found`
**Cause**: Warehouse doesn't exist or insufficient permissions
**Solution**:
- Verify warehouse name
- Check warehouse is running
- Ensure USAGE permission on warehouse

### Query Errors

#### SQL Syntax Error
**Error**: `SQL syntax error`
**Cause**: Invalid SQL syntax in query
**Solution**:
- Check SQL syntax
- Use SQL validation tools
- Review query structure

#### Permission Denied
**Error**: `Permission denied`
**Cause**: Insufficient privileges for operation
**Solution**:
- Check user permissions
- Verify object ownership
- Contact Snowflake admin for access

### Configuration Errors

#### Profile Not Found
**Error**: `Profile not found`
**Cause**: Profile doesn't exist in Snowflake CLI config
**Solution**:
- List profiles: `snow connection list`
- Create profile: `snow connection add`
- Check profile name spelling

#### Invalid Configuration
**Error**: `Invalid configuration`
**Cause**: Malformed configuration file
**Solution**:
- Validate TOML syntax
- Check required fields
- Use configuration guide

## Error Handling Modes

### Compact Mode (Default)
- Shows essential error information
- Saves 70% tokens for AI assistants
- Focuses on actionable solutions

### Verbose Mode
- Shows detailed error information
- Includes stack traces
- Useful for debugging

Enable verbose mode via environment variable:
```bash
export SNOWCLI_MCP_LOG_LEVEL=DEBUG
igloo-mcp --profile my-profile
```

## Troubleshooting Steps

### 1. Verify Prerequisites
```bash
# Check Python version
python --version

# Check Snowflake CLI
snow --version

# Check Igloo MCP installation
python -c "import igloo_mcp; print(igloo_mcp.__version__)"
```

### 2. Test Basic Connectivity
```bash
# Test Snowflake CLI connection directly
snow sql -q "SELECT CURRENT_USER()" --connection my-profile

# Test via Python API
python -c "from igloo_mcp import QueryService; print(QueryService(profile='my-profile'))"

# Or use MCP tools in your AI assistant:
# "Test my Snowflake connection"
# "Execute query: SELECT 1"
```

### 3. Check Configuration
```bash
# List profiles
snow connection list

# Show profile details
snow connection show my-profile
```

### 4. Enable Debug Logging
```bash
# Set debug environment variable for MCP server
export SNOWCLI_MCP_LOG_LEVEL=DEBUG

# Start MCP server with debug logging
igloo-mcp --profile my-profile

# Or enable debug in Python API
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Getting Help

### Self-Service
1. Check this error catalog
2. Review [Configuration Guide](../configuration.md)
3. Check [Getting Started Guide](../getting-started.md)

### Community Support
- GitHub Issues: Report bugs and request features
- GitHub Discussions: Ask questions and share solutions
- Documentation: Comprehensive guides and examples

### Professional Support
- Contact maintainers for critical issues
- Enterprise support available for commercial use

## Error Reporting

When reporting errors, please include:

1. **Error Message**: Exact error text
2. **Command**: Command that caused the error
3. **Environment**: Python version, OS, Snowflake CLI version
4. **Configuration**: Relevant config (sanitized)
5. **Steps to Reproduce**: Clear reproduction steps
6. **Expected Behavior**: What should happen
7. **Actual Behavior**: What actually happened

### Example Error Report
```markdown
## Error Report

**Error**: JWT token invalid
**Command**: MCP tool `test_connection` via AI assistant
**Environment**: Python 3.12, macOS, Snowflake CLI 2.0.0, Igloo MCP 0.3.0
**Steps**:
1. Generated key pair with openssl
2. Uploaded public key to Snowflake
3. Created profile with private key
4. Ran verify command
**Expected**: Successful verification
**Actual**: JWT token invalid error
```

---

*For additional help, see the [Getting Started Guide](../getting-started.md) or [Configuration Guide](../configuration.md).*
