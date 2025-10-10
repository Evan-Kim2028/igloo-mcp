# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-07

### BREAKING CHANGES

**🐻‍❄️ Package Rebrand: snowcli-tools → igloo-mcp**

The package has been renamed to better reflect its MCP-first architecture and create a unique brand identity.

#### Changed
- **Package name**: `snowcli-tools` → `igloo-mcp`
- **Import namespace**: `from snowcli_tools` → `from igloo_mcp`
- **PyPI package**: `pip install snowcli-tools` → `pip install igloo-mcp`
- **MCP command**: `snowcli-mcp` → `igloo-mcp`
- **GitHub repository**: `Evan-Kim2028/snowcli-tools` → `Evan-Kim2028/igloo-mcp`

**CLI Interface Removed**

The legacy CLI interface (`nanuk` command) has been removed. Igloo is now MCP-only.

#### Removed
- `nanuk` CLI command and all subcommands
- `src/igloo_mcp/cli.py` and `src/igloo_mcp/commands/` directory (~774 LOC)
- CLI-specific dependency: `click>=8.0.0`
- CLI-specific tests

#### Migration
- **Rebrand migration**: See [Migration Guide](docs/migration-guide.md) for package name changes and CLI to MCP migration
- **CLI migration**: See [CLI Migration Guide](docs/cli-to-mcp-migration.md) for transitioning to MCP tools
- All CLI functionality is available through MCP tools (see table in migration guide)

#### Rationale
- Package name is "nanuk-**mcp**" - should be MCP-only
- Reduces codebase by 774 LOC (40% reduction in interface code)
- Eliminates user confusion about which interface to use
- Aligns with AI-first architecture

#### Why "Nanuk"?
- 🐻‍❄️ Nanuk (polar bear in Inuit) connects to Snowflake's arctic theme
- 🎯 MCP-first: Name reflects focus on Model Context Protocol
- ✨ Unique & memorable: Stands out in the MCP ecosystem
- 🚀 Future-proof: Positions as premier Snowflake MCP provider

## [1.9.0] - 2025-01-04

### Phase 1: Code Simplification (Completed)

#### Added
- New simplified lineage models: `models.py`, `traversal.py`, `format.py` (~400 LOC total)
- Consolidated `health.HealthCheckTool` combining health_check, check_profile_config, and get_resource_status
- Cortex AI availability check in health tool (`include_cortex` parameter)
- Simplified `test_connection` tool as lightweight wrapper
- Migration guide: `docs/v1.9.0_migration.md`

#### Changed
- Lineage module reduced from 6,874 LOC to ~400 LOC (94% reduction)
- Health tools reduced from 5 tools (426 LOC) to 2 tools (150 LOC)
- `LineageGraph` aliased to `Graph` for backward compatibility
- `query_lineage` tool updated to use simplified lineage API

#### Removed
- `column_parser.py` (584 LOC) - Column-level lineage (too granular for common use cases)
- `cross_db.py` (509 LOC) - Cross-database lineage (niche use case)
- `impact.py` (830 LOC) - Impact analysis (move to optional package in future)
- `history.py` (889 LOC) - Lineage history tracking (complex, rarely used)
- `transformations.py` (~600 LOC) - Transformation metadata (overlaps with column parser)
- `external.py` (~400 LOC) - External source mapping (not implemented)
- `check_resource_dependencies` MCP tool (88 LOC) - Confusing API, rarely used
- `check_profile_config` MCP tool - Merged into HealthCheckTool
- `get_resource_status` MCP tool - Merged into HealthCheckTool

**Total Phase 1 Impact**: -4,088 LOC (66% code reduction)

### Phase 2: Incremental Catalog Building (Completed)

#### Added
- `catalog/incremental.py` (~500 LOC) - LAST_DDL-based delta detection
- `IncrementalCatalogBuilder` class for smart caching
- `build_incremental_catalog()` convenience function
- Hybrid querying (INFORMATION_SCHEMA + ACCOUNT_USAGE)
- Catalog metadata tracking (`_catalog_metadata.json`)
- Automatic fallback to full refresh when needed

#### Features
- **10-20x faster catalog refreshes** - Only updates changed objects
- **LAST_DDL detection** - Uses INFORMATION_SCHEMA.TABLES.LAST_DDL column
- **Hybrid approach** - Combines INFORMATION_SCHEMA (fast) with ACCOUNT_USAGE (complete)
- **Safety margin** - 3-hour buffer for ACCOUNT_USAGE latency
- **Automatic fallback** - Full refresh if metadata is old (>7 days) or corrupted
- **Backward compatible** - Works with existing catalog format

#### Changed
- `catalog/__init__.py` - Exported new incremental builder functions
- Updated documentation to reference incremental builds

#### Performance
Based on validated testing (583 tables, 10 changes in 7 days):
- **First build**: Same as before (~5 min for 1000 tables)
- **Refresh with 10 changes**: 5 min → 5 sec (**60x faster**)
- **Refresh with 0 changes**: 5 min → 2 sec (**150x faster**)
- **Refresh with 100 changes**: 5 min → 1 min (**5x faster**)

**Total Phase 2 Impact**: +500 LOC, 10-20x performance improvement

---

## [1.4.5] - 2025-09-27

### Added
- **🎯 Complete Profile Validation Implementation**: Full rollout of enhanced profile validation system
  - All profile validation features from v1.4.4 now fully implemented and tested
  - Comprehensive documentation suite with troubleshooting guides and quick-start materials
  - New MCP diagnostic tools: `health_check`, `check_profile_config`, `get_resource_status`, `check_resource_dependencies`
  - Enhanced error handling with MCP-compliant structured responses
  - Real-time health monitoring with caching and performance optimization

### Enhanced
- **📚 Comprehensive Documentation Package**:
  - `docs/profile_troubleshooting_guide.md` - Complete troubleshooting reference with before/after examples
  - `docs/profile_validation_quickstart.md` - Step-by-step setup guide for new users
  - `docs/mcp_diagnostic_tools.md` - Complete API reference for diagnostic tools
  - Enhanced README.md and MCP server user guide with practical examples
- **🏥 Production-Ready Health Monitoring**:
  - MCPHealthMonitor with comprehensive component tracking
  - MCPResourceManager for dependency-aware resource management
  - Structured error responses with specific error codes (-32001 to -32005)
  - Performance optimizations with TTL-based caching

### Fixed
- **🎯 User Experience Issues**: Complete elimination of misleading timeout errors for profile configuration problems
- **🚀 Development Experience**: Enhanced error messages with immediate, actionable guidance
- **⚡ Performance**: Optimized profile validation with caching and modern Python patterns

## [1.4.4] - 2025-09-27

### Added
- **🎯 Enhanced Profile Validation System**: Revolutionary improvement to user experience
  - Startup profile validation that catches configuration issues immediately
  - Clear, actionable error messages instead of confusing timeout errors
  - Modern Python 3.12+ implementation with performance caching
  - Structured error responses following MCP JSON-RPC 2.0 standards
- **🏥 Comprehensive Health Monitoring**: New diagnostic tools for MCP server
  - `health_check`: Real-time server health status with component details
  - `check_profile_config`: Profile validation and configuration recommendations
  - `get_resource_status`: Resource availability and dependency checking
  - `check_resource_dependencies`: Specific resource dependency validation
- **🔧 Advanced Error Handling Infrastructure**:
  - Circuit breaker pattern for fault-tolerant Snowflake operations
  - Comprehensive error categorization (Connection, Permission, Timeout, Configuration)
  - `ProfileConfigurationError` with rich context and available profiles
  - MCP-compliant error codes (-32001 to -32005) with structured data
- **📚 Comprehensive Documentation Suite**:
  - Profile Troubleshooting Guide with before/after comparisons
  - Profile Validation Quick-Start Guide with step-by-step setup
  - MCP Diagnostic Tools Reference with API documentation
  - Enhanced user guides with v1.4.4+ features and examples
- **🔬 Extensive Testing Infrastructure**:
  - Robust service layer with health monitoring and safe execution patterns
  - Enhanced MCP server configuration examples with multiple setup options
  - Extensive test coverage for new reliability infrastructure (~80 new tests)

### Changed
- **🚀 User Experience Transformation**:
  - Profile validation errors now provide immediate, clear feedback
  - MCP server startup includes proactive profile validation
  - Error messages include specific available profiles and next steps
  - Documentation updated with practical troubleshooting examples
- **⚡ Performance Optimizations**:
  - Profile validation caching with `@functools.lru_cache`
  - mtime-based configuration file caching for efficiency
  - Modern Python 3.12+ patterns (match statements, union types)
- **📖 Documentation Enhancements**:
  - Updated README.md with comprehensive profile management section
  - Enhanced MCP server user guide with health monitoring capabilities
  - Features overview updated with v1.4.4+ improvements
  - Added cross-references between related documentation

### Fixed
- **🐛 Critical UX Issues**:
  - Eliminated misleading timeout errors for profile configuration problems
  - Fixed silent fallback to non-existent "default" profile
  - Resolved late error detection that confused users
  - Improved error messaging accessibility and clarity
- **🔧 Technical Improvements**:
  - Type annotation errors in circuit breaker and error handling modules
  - Code formatting consistency across all Python files
  - MCP configuration format and environment variable documentation
  - Import optimization and unused code removal

## [1.4.3] - 2025-09-26

### Added
- Session management helpers that snapshot and restore Snowflake context so MCP
  overrides stay scoped to a single tool call.
- `--enable-cli-bridge` flag to optionally expose the legacy `snow` CLI bridge
  tool; the FastMCP server defaults to the in-process connector tools.
- `local_sf_test/` smoke harness that fetches the latest rows from
  `object_parquet2` for visual verification.

### Changed
- MCP argument parsing now treats missing defaults as `None`, preventing
  help-string values from becoming accidental overrides.
- Snowcli MCP tools reuse the official `SnowflakeService` connection under a
  scoped lock rather than opening ad-hoc sessions.
- Documentation updated with the new flag, session model, and smoke-test
  instructions.

## [1.3.0] - 2024-09-24

### Added
- **MCP (Model Context Protocol) Server Support**: Complete integration with AI assistants
  - New `snowflake-cli mcp` command to run MCP server
  - 7 MCP tools: execute_query, preview_table, build_catalog, query_lineage, build_dependency_graph, test_connection, get_catalog_summary
  - Optional dependency installation via `pip install snowcli-tools[mcp]`
  - stdio transport with JSON-RPC 2.0 protocol
  - Compatible with VS Code, Cursor, Claude Code, and other MCP clients

- **Comprehensive MCP Documentation**
  - `/docs/mcp/` directory with technical and user guides
  - ASCII-based architecture diagrams for GitHub compatibility
  - Complete setup and integration instructions
  - Real-world DeFi sample dataset examples

- **Sample Data Infrastructure**
  - `/examples/sample_data/` with production DeFi pipeline DDL
  - `dex_trades_stable` table as primary example (224M+ records)
  - Automated setup script for sample dataset installation
  - Complete database structure for DEX trading analytics

- **Enhanced Lineage Analysis**
  - Improved partial object lookup for lineage queries
  - Better error handling for missing objects
  - HTML visualization support for lineage graphs
  - Support for task objects in lineage traversal

### Changed
- Updated all documentation to use real DeFi examples instead of generic placeholders
- Moved MCP configuration to examples folder as template
- Enhanced README with MCP installation and usage instructions
- Improved error messages and user feedback across MCP tools

### Fixed
- Large file handling in git repository (removed oversized lineage_graph.json)
- Pre-commit hook compliance (formatting, imports, trailing whitespace)
- Unused variable warnings in MCP server code

### Technical Details
- MCP server runs as async stdio server using `mcp.server.stdio`
- Integrates with existing SnowCLI and LineageQueryService infrastructure
- Supports all existing snowcli-tools functionality through MCP protocol
- Maintains backward compatibility with CLI usage

## [1.2.x] - Previous Versions
- Core lineage analysis and catalog building functionality
- Dependency graph generation
- Snowflake CLI integration
- Basic documentation and examples
