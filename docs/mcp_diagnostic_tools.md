# MCP Diagnostic Tools Reference (v0.3.0)

## Overview

Igloo MCP v0.3.0 provides comprehensive diagnostic tools for the MCP server that provide real-time health monitoring, profile validation, and resource dependency checking. These tools help quickly identify and resolve configuration issues.

> **⚠️ Important**: In v0.3.0, the diagnostic tools `check_profile_config`, `get_resource_status`, and `check_resource_dependencies` have been **consolidated into the `health_check` tool**. Use `health_check` with appropriate parameters (`include_profile=True`, `include_catalog=True`) to access the same functionality. The deprecated tools are documented below for reference only.

## Tool Categories

### 🏥 Health Monitoring Tools
- [`health_check`](#health_check) - Comprehensive server health status (includes profile validation and resource availability)

### 🔗 Connection Tools
- [`test_connection`](#test_connection) - Basic connection testing

## Detailed Tool Documentation

### `health_check`

**Purpose**: Provides comprehensive health status of all MCP server components.

**Parameters**: None

**Usage Examples**:
```
AI: "Check the MCP server health"
AI: "What is the overall health status?"
AI: "Give me a health report for the snowflake server"
```

**Response Format**:
```json
{
  "overall_status": "healthy",
  "connection": {
    "status": "connected",
    "connected": true,
    "profile": "dev",
    "warehouse": "COMPUTE_WH",
    "database": "DEV_DB",
    "schema": "PUBLIC",
    "role": "DEV_ROLE"
  },
  "profile": {
    "status": "valid",
    "profile": "dev",
    "config": {
      "config_path": "/Users/user/.config/snowflake/config.toml",
      "config_exists": true,
      "available_profiles": ["dev", "staging", "prod"],
      "default_profile": "dev",
      "current_profile": "dev",
      "profile_count": 3
    },
    "authentication": {
      "authenticator": "externalbrowser",
      "is_externalbrowser": true,
      "is_okta_url": false
    }
  },
  "resources": {
    "status": "healthy",
    "available": {
      "catalog": true,
      "lineage": true,
      "cortex_search": false,
      "dependency_graph": true
    },
    "dependencies_met": true
  },
  "system": {
    "timestamp": 1673524800.0,
    "server_uptime": 3600.5
  },
  "diagnostics": {
    "storage_paths": {
      "scope": "global",
      "base_directory": "/Users/user/.igloo_mcp",
      "query_history": "/Users/user/.igloo_mcp/logs/doc.jsonl",
      "artifacts": "/Users/user/.igloo_mcp/logs/artifacts",
      "cache": "/Users/user/.igloo_mcp/logs/artifacts/cache",
      "reports": "/Users/user/.igloo_mcp/reports",
      "catalogs": "/Users/user/.igloo_mcp/catalogs",
      "namespaced": false
    }
  }
}
```

**Status Meanings**:
- **healthy**: All components functioning normally
- **degraded**: Some non-critical issues detected
- **unhealthy**: Critical issues preventing normal operation

**Common Use Cases**:
- Regular health monitoring
- Troubleshooting connection issues
- Pre-flight checks before important operations
- Monitoring server performance

---

### `check_profile_config` ⚠️ DEPRECATED

> **Deprecated in v0.3.0**: This tool has been consolidated into `health_check`. Use `health_check(include_profile=True)` instead.

**Purpose**: Validates Snowflake profile configuration and provides detailed diagnostics.

**Parameters**: None

**Replacement**: Use `health_check` with `include_profile=True` parameter

**Usage Examples**:
```
AI: "Check my Snowflake profile configuration"
AI: "Validate the current profile settings"
AI: "What profiles are available?"
AI: "Diagnose profile configuration issues"
```

**Response Format**:
```json
{
  "current_profile": {
    "name": "dev",
    "is_valid": true,
    "validation_status": "success",
    "last_validated": 1673524800.0
  },
  "available_profiles": [
    {
      "name": "dev",
      "is_default": true,
      "is_valid": true,
      "account": "mycompany-dev",
      "warehouse": "DEV_WH",
      "database": "DEV_DB",
      "authentication": "key_pair"
    },
    {
      "name": "prod",
      "is_default": false,
      "is_valid": true,
      "account": "mycompany-prod",
      "warehouse": "PROD_WH",
      "database": "PROD_DB",
      "authentication": "oauth"
    }
  ],
  "configuration": {
    "config_file_path": "/Users/user/.config/snowflake/config.toml",
    "config_file_exists": true,
    "config_file_readable": true,
    "last_modified": 1673520000.0
  },
  "recommendations": [
    "Profile configuration is valid",
    "Consider setting up a production profile for deployment"
  ]
}
```

**Error Response Example**:
```json
{
  "error": {
    "code": -32004,
    "message": "Profile validation failed",
    "data": {
      "error_type": "profile_not_found",
      "profile_name": "nonexistent",
      "available_profiles": ["dev", "prod"],
      "config_path": "/Users/user/.config/snowflake/config.toml",
      "suggestions": [
        "Set SNOWFLAKE_PROFILE to one of: dev, prod",
        "Create the missing profile with: snow connection add --connection-name nonexistent",
        "Check the configuration file exists and is readable"
      ]
    }
  }
}
```

**Common Use Cases**:
- Diagnosing profile configuration issues
- Listing available profiles
- Validating environment setup
- Getting configuration recommendations

---

### `get_resource_status` ⚠️ DEPRECATED

> **Deprecated in v0.3.0**: This tool has been consolidated into `health_check`. Use `health_check(include_catalog=True)` instead.

**Purpose**: Checks availability of all MCP resources and their dependencies.

**Parameters**: None

**Replacement**: Use `health_check` with `include_catalog=True` parameter

**Usage Examples**:
```
AI: "Check resource availability"
AI: "Are all MCP resources available?"
AI: "What resources can I use right now?"
AI: "Show me the resource status"
```

**Response Format**:
```json
{
  "overall_status": "healthy",
  "resources": {
    "catalog": {
      "available": true,
      "status": "ready",
      "dependencies": ["profile", "connection"],
      "dependencies_met": true,
      "last_checked": 1673524800.0,
      "performance": {
        "avg_response_time_ms": 1200,
        "success_rate": 0.98
      }
    },
    "lineage": {
      "available": true,
      "status": "ready",
      "dependencies": ["profile", "connection", "catalog"],
      "dependencies_met": true,
      "last_checked": 1673524800.0,
      "cache_status": "warm"
    },
    "cortex_search": {
      "available": false,
      "status": "unavailable",
      "dependencies": ["profile", "connection", "cortex_enabled"],
      "dependencies_met": false,
      "error": "Cortex AI not enabled for this account",
      "last_checked": 1673524800.0
    },
    "dependency_graph": {
      "available": true,
      "status": "ready",
      "dependencies": ["profile", "connection"],
      "dependencies_met": true,
      "last_checked": 1673524800.0
    }
  },
  "dependency_summary": {
    "profile": {
      "status": "healthy",
      "required_by": ["catalog", "lineage", "cortex_search", "dependency_graph"]
    },
    "connection": {
      "status": "healthy",
      "required_by": ["catalog", "lineage", "cortex_search", "dependency_graph"]
    },
    "catalog": {
      "status": "healthy",
      "required_by": ["lineage"]
    },
    "cortex_enabled": {
      "status": "unavailable",
      "required_by": ["cortex_search"]
    }
  }
}
```

**Resource Status Values**:
- **ready**: Resource fully available and functional
- **initializing**: Resource starting up or loading
- **degraded**: Resource available but with limited functionality
- **unavailable**: Resource not accessible due to missing dependencies
- **error**: Resource failed with specific error

**Common Use Cases**:
- Pre-operation dependency checking
- Understanding why certain tools might fail
- Resource availability monitoring
- Performance tracking

---

### `check_resource_dependencies` ⚠️ DEPRECATED

> **Deprecated in v0.3.0**: This tool has been consolidated into `health_check`. Use `health_check(include_catalog=True)` instead.

**Purpose**: Validates dependencies for a specific resource or all resources.

**Parameters**:
- `resource_name` (optional): Specific resource to check ("catalog", "lineage", "cortex_search", "dependency_graph")

**Replacement**: Use `health_check` with `include_catalog=True` parameter

**Usage Examples**:
```
AI: "Check dependencies for the catalog resource"
AI: "What does the lineage tool need to work?"
AI: "Check all resource dependencies"
AI: "Validate cortex search dependencies"
```

**Response Format (Specific Resource)**:
```json
{
  "resource": "lineage",
  "status": "ready",
  "dependencies": {
    "profile": {
      "required": true,
      "status": "satisfied",
      "details": "Profile 'dev' is valid and accessible"
    },
    "connection": {
      "required": true,
      "status": "satisfied",
      "details": "Snowflake connection is healthy"
    },
    "catalog": {
      "required": true,
      "status": "satisfied",
      "details": "Catalog data is available and fresh"
    }
  },
  "recommendations": [
    "All dependencies satisfied - lineage analysis is ready to use",
    "Consider refreshing catalog if data is more than 24 hours old"
  ],
  "ready_to_use": true
}
```

**Response Format (All Resources)**:
```json
{
  "dependency_matrix": {
    "catalog": {
      "required_dependencies": ["profile", "connection"],
      "optional_dependencies": [],
      "status": "ready",
      "blocking_issues": []
    },
    "lineage": {
      "required_dependencies": ["profile", "connection", "catalog"],
      "optional_dependencies": ["fresh_catalog_data"],
      "status": "ready",
      "blocking_issues": []
    },
    "cortex_search": {
      "required_dependencies": ["profile", "connection", "cortex_enabled"],
      "optional_dependencies": [],
      "status": "unavailable",
      "blocking_issues": ["Cortex AI not enabled for account"]
    }
  },
  "global_dependencies": {
    "profile": {
      "status": "healthy",
      "affects": ["catalog", "lineage", "cortex_search", "dependency_graph"]
    },
    "connection": {
      "status": "healthy",
      "affects": ["catalog", "lineage", "cortex_search", "dependency_graph"]
    }
  }
}
```

**Common Use Cases**:
- Understanding why a specific tool isn't working
- Pre-operation validation
- Troubleshooting complex dependency chains
- Planning resource usage

---

### `test_connection`

**Purpose**: Basic Snowflake connection testing.

**Parameters**: None

**Usage Examples**:
```
AI: "Test the Snowflake connection"
AI: "Is the database connection working?"
AI: "Check if I can connect to Snowflake"
```

**Response Format**:
```json
{
  "connection_status": "healthy",
  "profile_used": "dev",
  "connection_details": {
    "account": "mycompany-dev",
    "warehouse": "DEV_WH",
    "database": "DEV_DB",
    "schema": "PUBLIC",
    "role": "ANALYST_ROLE"
  },
  "test_results": {
    "authentication": "success",
    "warehouse_access": "success",
    "database_access": "success",
    "schema_access": "success",
    "response_time_ms": 234
  },
  "snowflake_info": {
    "version": "8.15.2",
    "region": "us-west-2",
    "edition": "ENTERPRISE"
  }
}
```

## Error Handling

### Error Code Reference

| Error Code | Category | Description |
|------------|----------|-------------|
| -32001 | Configuration Error | Profile configuration invalid |
| -32002 | Connection Error | Network or connectivity issue |
| -32003 | Authentication Error | Credentials invalid or expired |
| -32004 | Profile Error | Profile not found or misconfigured |
| -32005 | Resource Unavailable | Required resources not accessible |

### Common Error Scenarios

**Profile Not Found**:
```json
{
  "error": {
    "code": -32004,
    "message": "Profile validation failed: Profile 'missing' not found",
    "data": {
      "available_profiles": ["dev", "prod"],
      "suggestions": ["Set SNOWFLAKE_PROFILE to existing profile", "Create missing profile"]
    }
  }
}
```

**Connection Failure**:
```json
{
  "error": {
    "code": -32002,
    "message": "Connection health check failed",
    "data": {
      "error_details": "Network timeout after 30 seconds",
      "suggestions": ["Check network connectivity", "Verify firewall settings"]
    }
  }
}
```

**Resource Unavailable**:
```json
{
  "error": {
    "code": -32005,
    "message": "Resource 'lineage' unavailable",
    "data": {
      "missing_dependencies": ["catalog"],
      "suggestions": ["Run build_catalog tool first", "Ensure profile has database access"]
    }
  }
}
```

## Performance Characteristics

### Caching Behavior

**Health Check Caching**:
- **TTL**: 30 seconds by default
- **Cache key**: Profile name + component type
- **Invalidation**: Manual refresh or TTL expiry

**Resource Status Caching**:
- **TTL**: 60 seconds by default
- **Cache key**: Resource name + dependency state
- **Invalidation**: Dependency change or TTL expiry

### Response Times

**Typical Response Times**:
- `health_check`: 50-200ms (cached), 500-2000ms (fresh)
- `test_connection`: 200-1000ms

## Configuration Options

### Environment Variables

```bash
# Adjust caching behavior
export SNOWCLI_MCP_HEALTH_CACHE_TTL=30      # Health check cache TTL (seconds)
export SNOWCLI_MCP_RESOURCE_CACHE_TTL=60    # Resource status cache TTL (seconds)

# Enable detailed logging
export SNOWCLI_MCP_LOG_LEVEL=DEBUG          # Debug logging for diagnostics
```

### Cache Control

**Force Refresh Health Check**:
```
AI: "Force refresh the health check and show current status"
```

**Clear Cache**:
The cache is automatically managed but can be effectively cleared by waiting for TTL expiry or restarting the MCP server.

## Integration Examples

### Automated Health Monitoring

```python
# Example AI assistant workflow
def check_system_health():
    health = call_mcp_tool("health_check")
    if health["status"] != "healthy":
        profile_check = call_mcp_tool("check_profile_config")
        health_with_resources = call_mcp_tool("health_check", {"include_profile": True, "include_catalog": True})
        return diagnose_issues(health, health_with_resources)
    return "System is healthy"
```

### Pre-Operation Validation

```python
def validate_before_catalog_build():
    health = call_mcp_tool("health_check", {"include_profile": True, "include_catalog": True})
    if not health.get("system", {}).get("healthy", False):
        return fix_dependencies(health.get("recommendations", []))
    return "Ready to build catalog"
```

## Best Practices

### Regular Health Monitoring
- Check health status before important operations
- Monitor trends in response times
- Set up alerts for degraded status

### Dependency Management
- Validate dependencies before running complex operations
- Understand the dependency hierarchy
- Fix issues at the root dependency level

### Error Handling
- Always check error codes for specific handling
- Use suggestions provided in error responses
- Implement retry logic with exponential backoff

### Performance Optimization
- Leverage caching for frequent checks
- Use specific resource checks instead of full status when possible
- Monitor and tune cache TTL values based on usage patterns

The diagnostic tools provide comprehensive visibility into the MCP server's health and configuration state, making it much easier to identify and resolve issues quickly.
