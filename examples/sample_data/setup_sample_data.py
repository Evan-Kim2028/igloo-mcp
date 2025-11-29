#!/usr/bin/env python3
"""
Setup script for the DeFi DEX trading sample dataset.

This script installs the sample dataset structure and catalog metadata
to demonstrate igloo-mcp capabilities with real-world data patterns.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from igloo_mcp.config import get_config
from igloo_mcp.snow_cli import SnowCLI, SnowCLIError


def setup_logging():
    """Configure logging for setup script."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    return logging.getLogger(__name__)


def load_ddl_files(ddl_dir: Path) -> Dict[str, str]:
    """Load all SQL DDL files from the ddl directory."""
    ddl_files = {}

    sql_files = [
        "dex_trades_stable.sql",
        "coin_info.sql",
        "btc_dex_trades_usd_dt.sql",
        "filtered_dex_trades_view.sql",
    ]

    for sql_file in sql_files:
        file_path = ddl_dir / sql_file
        if file_path.exists():
            with open(file_path, "r") as f:
                ddl_files[sql_file] = f.read()
        else:
            logging.warning(f"DDL file not found: {file_path}")

    return ddl_files


def create_database_structure(snow_cli: SnowCLI, logger: logging.Logger) -> bool:
    """Create the sample database and schema structure."""
    try:
        logger.info("Creating sample database structure...")

        # Create database and schemas
        queries = [
            "CREATE DATABASE IF NOT EXISTS DEFI_SAMPLE_DB",
            "CREATE SCHEMA IF NOT EXISTS DEFI_SAMPLE_DB.RAW",
            "CREATE SCHEMA IF NOT EXISTS DEFI_SAMPLE_DB.PROCESSED",
            "CREATE SCHEMA IF NOT EXISTS DEFI_SAMPLE_DB.ANALYTICS",
            "USE DATABASE DEFI_SAMPLE_DB",
        ]

        for query in queries:
            logger.info(f"Executing: {query}")
            result = snow_cli.run_query(query, output_format="table")
            if result.returncode != 0:
                logger.error(f"Failed to execute: {query}")
                logger.error(f"Error: {result.raw_stderr}")
                return False

        logger.info("✅ Database structure created successfully")
        return True

    except SnowCLIError as e:
        logger.error(f"Failed to create database structure: {e}")
        return False


def create_sample_tables(snow_cli: SnowCLI, ddl_files: Dict[str, str], logger: logging.Logger) -> bool:
    """Create sample tables using the DDL files."""
    try:
        logger.info("Creating sample tables...")

        # Modify DDL to use sample database
        for filename, ddl in ddl_files.items():
            logger.info(f"Creating objects from {filename}...")

            # Replace references to use sample database
            modified_ddl = ddl.replace(
                "PIPELINE_V2_GROOT_DB.PIPELINE_V2_GROOT_SCHEMA",
                "DEFI_SAMPLE_DB.PROCESSED",
            ).replace("PIPELINE_V2_GROOT_DB", "DEFI_SAMPLE_DB")

            # Execute the DDL
            try:
                result = snow_cli.run_query(modified_ddl, output_format="table")
                if result.returncode != 0:
                    logger.warning(f"DDL execution had issues: {result.raw_stderr}")
                    # Continue anyway - some errors might be expected (missing source tables)
                else:
                    logger.info(f"✅ Successfully processed {filename}")

            except SnowCLIError as e:
                logger.warning(f"Expected error for {filename} (missing source data): {e}")
                # This is expected since we don't have the raw data
                continue

        logger.info("✅ Sample table structure created")
        return True

    except Exception as e:
        logger.error(f"Failed to create sample tables: {e}")
        return False


def generate_sample_catalog(snow_cli: SnowCLI, logger: logging.Logger) -> bool:
    """Generate a sample catalog for the created objects."""
    try:
        logger.info("Generating sample catalog...")

        # Use igloo-mcp to catalog the sample database
        from igloo_mcp.catalog import build_catalog

        catalog_dir = Path(__file__).parent / "catalog"
        catalog_dir.mkdir(exist_ok=True)

        # Build catalog for our sample database
        totals = build_catalog(
            str(catalog_dir),
            database="DEFI_SAMPLE_DB",
            account_scope=False,
            incremental=False,
            output_format="jsonl",
            include_ddl=True,
            max_ddl_concurrency=4,
            catalog_concurrency=8,
            export_sql=False,
        )

        logger.info(f"✅ Catalog generated successfully: {totals}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate catalog: {e}")
        return False


def create_lineage_example(snow_cli: SnowCLI, logger: logging.Logger) -> bool:
    """Create lineage analysis for the sample data."""
    try:
        logger.info("Generating lineage examples...")

        from igloo_mcp.lineage import LineageQueryService

        # Set up lineage service
        catalog_dir = str(Path(__file__).parent / "catalog")
        lineage_dir = str(Path(__file__).parent / "lineage")
        Path(lineage_dir).mkdir(exist_ok=True)

        service = LineageQueryService(catalog_dir, lineage_dir)

        # Try to build lineage graph
        try:
            # This might fail if we don't have enough data, but that's okay
            result = service.object_subgraph("DEFI_SAMPLE_DB.PROCESSED.DEX_TRADES_STABLE", direction="both", depth=2)

            logger.info(f"✅ Lineage example created with {len(result.graph.nodes)} nodes")

        except KeyError as e:
            logger.info(f"Lineage generation skipped (expected): {e}")
            # Create a simple example file instead
            example_lineage = {
                "object": "DEFI_SAMPLE_DB.PROCESSED.DEX_TRADES_STABLE",
                "description": "Main fact table for DEX trading data",
                "upstream": [
                    "DEFI_SAMPLE_DB.RAW.OBJECT_CHANGES",
                    "DEFI_SAMPLE_DB.RAW.DEX_EVENTS",
                ],
                "downstream": [
                    "DEFI_SAMPLE_DB.ANALYTICS.FILTERED_DEX_TRADES_VIEW",
                    "DEFI_SAMPLE_DB.ANALYTICS.BTC_DEX_TRADES_USD_DT",
                ],
            }

            with open(Path(lineage_dir) / "example_lineage.json", "w") as f:
                json.dump(example_lineage, f, indent=2)

        return True

    except Exception as e:
        logger.error(f"Failed to create lineage examples: {e}")
        return False


def print_usage_instructions(logger: logging.Logger):
    """Print instructions for using the sample dataset."""
    logger.info("\n" + "=" * 60)
    logger.info("🎉 DeFi Sample Dataset Setup Complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("The sample dataset includes:")
    logger.info("• DEX_TRADES_STABLE - Main fact table (structure only)")
    logger.info("• COIN_INFO - Dynamic table for crypto metadata")
    logger.info("• FILTERED_DEX_TRADES_VIEW - Business logic view")
    logger.info("• BTC_DEX_TRADES_USD_DT - BTC-focused analytics")
    logger.info("")
    logger.info("Try these igloo-mcp MCP tools via your AI assistant:")
    logger.info("")
    logger.info("📊 Catalog Commands:")
    logger.info('  "Build a catalog for DEFI_SAMPLE_DB"')
    logger.info('  "Build a catalog for DEFI_SAMPLE_DB.ANALYTICS schema"')
    logger.info("")
    logger.info("🔗 Lineage Commands:")
    logger.info('  "Query lineage for DEX_TRADES_STABLE"')
    logger.info('  "Show upstream lineage for FILTERED_DEX_TRADES_VIEW"')
    logger.info("")
    logger.info("🕸️  Dependency Graph:")
    logger.info('  "Build dependency graph for DEFI_SAMPLE_DB"')
    logger.info('  "Generate dependency graph as JSON"')
    logger.info("")
    logger.info("🤖 MCP Server Examples:")
    logger.info("  'Show me the schema of DEX_TRADES_STABLE'")
    logger.info("  'What feeds into the BTC analytics table?'")
    logger.info("  'Build a catalog for the DeFi sample database'")
    logger.info("")
    logger.info("📚 Documentation:")
    logger.info("  See examples/sample_data/pipeline_documentation.md")
    logger.info("  See examples/sample_data/README.md")
    logger.info("")


def main():
    """Main setup function."""
    logger = setup_logging()

    logger.info("🚀 Setting up DeFi DEX Trading Sample Dataset")
    logger.info("=" * 50)

    try:
        # Initialize SnowCLI
        logger.info("Initializing Snowflake connection...")
        snow_cli = SnowCLI()
        get_config()  # Initialize configuration

        # Test connection
        if not snow_cli.test_connection():
            logger.error("❌ Failed to connect to Snowflake. Please check your configuration.")
            return 1

        logger.info("✅ Snowflake connection successful")

        # Load DDL files
        ddl_dir = Path(__file__).parent / "ddl"
        ddl_files = load_ddl_files(ddl_dir)

        if not ddl_files:
            logger.error("❌ No DDL files found. Please ensure DDL files exist.")
            return 1

        logger.info(f"✅ Loaded {len(ddl_files)} DDL files")

        # Create database structure
        if not create_database_structure(snow_cli, logger):
            logger.error("❌ Failed to create database structure")
            return 1

        # Create sample tables
        if not create_sample_tables(snow_cli, ddl_files, logger):
            logger.error("❌ Failed to create sample tables")
            return 1

        # Generate catalog
        if not generate_sample_catalog(snow_cli, logger):
            logger.warning("⚠️  Catalog generation had issues (this might be expected)")

        # Create lineage examples
        if not create_lineage_example(snow_cli, logger):
            logger.warning("⚠️  Lineage example creation had issues (this might be expected)")

        # Print usage instructions
        print_usage_instructions(logger)

        return 0

    except KeyboardInterrupt:
        logger.info("\n❌ Setup interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"❌ Unexpected error during setup: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
