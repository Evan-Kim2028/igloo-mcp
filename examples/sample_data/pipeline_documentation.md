# DeFi DEX Trading Data Pipeline Documentation

## Overview

This document describes the real-world data pipeline extracted from a DeFi (Decentralized Finance) trading analytics system. The pipeline processes decentralized exchange (DEX) trading data from multiple blockchain protocols and provides various analytical views for trading analysis.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES (Layer 0)                   │
├─────────────────────────────────────────────────────────────────┤
│  Raw Blockchain Data    │  DEX Events    │  External Price Data │
│  - Object changes       │  - Swap logs   │  - USD pricing       │
│  - State transitions    │  - Pool data   │  - Market data       │
└─────────────────┬───────────────┬───────────────────┬───────────┘
                  │               │                   │
                  ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RAW LAYER (Layer 1)                        │
├─────────────────────────────────────────────────────────────────┤
│          OBJECT_PARQUET2           │        PRICE_FEEDS         │
│      - 224M+ object changes        │     - External pricing     │
│      - Blockchain state data       │     - Market data feeds    │
│      - Transaction metadata        │     - Liquidity metrics    │
└─────────────┬─────────────┬────────┬─────────────────┬─────────┘
              │             │        │                 │
              ▼             │        ▼                 │
┌─────────────────────────────────────────────────────────────────┐
│                  PROCESSED LAYER (Layer 2)                     │
├─────────────────────────────────────────────────────────────────┤
│      COIN_INFO (Dynamic)          │    DEX_TRADES_STABLE       │
│   - Hourly metadata refresh       │   - 224M+ trading records  │ ◄──┘
│   - Token symbols & decimals      │   - Multi-protocol data    │
│   - Name normalization            │   - Enriched with metadata │
└─────────────┬─────────────────────┬─────────────────────────────┘
              │                     │
              │            ┌────────▼────────┐
              │            │                 │
              ▼            ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ANALYTICS LAYER (Layer 3)                     │
├─────────────────────────────────────────────────────────────────┤
│  FILTERED_DEX_TRADES_VIEW     │    BTC_DEX_TRADES_USD_DT       │
│  - Business logic filtering   │    - BTC-focused analytics     │
│  - User-initiated trades      │    - USD price calculations    │
│  - Complex EXISTS logic       │    - Daily refresh cycle      │
│                               │    - Multi-source joins       │
└─────────────────────────────────────────────────────────────────┘

Key Relationships:
• OBJECT_PARQUET2 → COIN_INFO (metadata extraction)
• COIN_INFO + Raw Events → DEX_TRADES_STABLE (fact table enrichment)
• DEX_TRADES_STABLE → FILTERED_DEX_TRADES_VIEW (business filtering)
• DEX_TRADES_STABLE + COIN_INFO + PRICE_FEEDS → BTC_DEX_TRADES_USD_DT (analytics)
```

## Data Flow & Lineage

### Layer 1: Raw Data Sources
- **OBJECT_PARQUET2**: Blockchain object state changes (224M+ records)
- **Raw DEX Events**: Transaction logs from DEX protocols
- **External Price Feeds**: USD pricing data

### Layer 2: Processed Data (Silver Layer)
- **COIN_INFO**: Dynamic table with cryptocurrency metadata (refreshes hourly)
- **DEX_TRADES_STABLE**: Main fact table containing all DEX trades with enriched metadata

### Layer 3: Analytics (Gold Layer)
- **FILTERED_DEX_TRADES_VIEW**: Business logic view showing only user-initiated trades
- **BTC_DEX_TRADES_USD_DT**: BTC-focused analytics with USD pricing (refreshes daily)

## Key Tables & Objects

### 1. DEX_TRADES_STABLE (Main Fact Table)

**Purpose**: Central repository for all DEX trading activity across multiple protocols

**Key Features**:
- **Volume**: 224+ million records (~16.7GB)
- **Clustering**: Optimized by `(timestamp_ms, protocol)` for time-series queries
- **Protocols**: aftermath, bluefin, bluemove, cetus, flowx, metastable
- **Auto-clustering**: Enabled for query performance
- **Tags**: Metadata management with DATA_OWNER, PROJECT, SUB_PROJECT

**Schema Highlights**:
```sql
PROTOCOL VARCHAR          -- DEX protocol name
TIMESTAMP_MS NUMBER       -- Transaction timestamp (milliseconds)
TRANSACTION_DIGEST VARCHAR -- Unique transaction ID
POOL_ID VARCHAR          -- Trading pool identifier
SENDER VARCHAR           -- Trader address
COIN_IN/COIN_OUT VARCHAR -- Token identifiers
AMOUNT_IN/AMOUNT_OUT NUMBER -- Raw amounts
COIN_*_SYMBOL VARCHAR    -- Human-readable token symbols
ADJUSTED_AMOUNT_* FLOAT  -- Decimal-adjusted amounts
A_TO_B BOOLEAN          -- Trade direction indicator
```

### 2. COIN_INFO (Dynamic Table)

**Purpose**: Cryptocurrency metadata with automatic updates

**Key Features**:
- **Refresh**: Incremental updates every hour
- **Source**: Derived from blockchain object changes
- **Deduplication**: Latest version per coin type using QUALIFY

**Business Logic**:
- Extracts coin metadata from blockchain objects
- Parses nested JSON for decimals, names, symbols
- Handles coin type normalization

### 3. FILTERED_DEX_TRADES_VIEW (Business Logic View)

**Purpose**: Identifies genuine user-initiated trades vs. routing/arbitrage

**Complex Logic**:
```sql
-- Only include trades where the input coin was actually
-- modified in the user's wallet during the transaction
WITH TransactionUserCoins AS (
    SELECT DISTINCT
        previous_transaction AS transaction_digest,
        CASE
            WHEN coin_type = '0x00...::sui::SUI' THEN '0x2::sui::SUI'
            ELSE coin_type
        END AS coin_type
    FROM OBJECT_PARQUET2
    WHERE coin_type IS NOT NULL
      AND previous_transaction IS NOT NULL
)
SELECT dts.*
FROM DEX_TRADES_STABLE dts
WHERE EXISTS (
    SELECT 1 FROM TransactionUserCoins tuc
    WHERE tuc.transaction_digest = dts.transaction_digest
      AND tuc.coin_type = dts.normalized_coin_in
)
```

**Business Value**: Filters out intermediate swaps in multi-hop routes, showing only entry-point trades

### 4. BTC_DEX_TRADES_USD_DT (Dynamic Table)

**Purpose**: BTC-focused analytics with USD pricing

**Key Features**:
- **Refresh**: Full refresh daily (1-day target lag)
- **Complex Logic**: Multi-CTE structure with pool filtering, price joins
- **Dependencies**: References multiple tables (liquidity, prices, pool names)

**Business Logic**:
1. **Pool Filtering**: Identify pools containing BTC variants
2. **Price Enrichment**: Join with daily price averages
3. **USD Calculations**: Convert token amounts to USD values
4. **Pool Naming**: Derive human-readable pool names

## Data Quality & Governance

### Tagging Strategy
- **DATA_OWNER**: 'evan_kim' → Contact for data issues
- **PROJECT**: 'defi' → Business domain
- **SUB_PROJECT**: 'dex' → Specific use case

### Performance Optimizations
- **Clustering**: Time-series clustering on main fact table
- **Auto-clustering**: Enabled for dynamic optimization
- **Incremental Refresh**: Efficient updates for dimension tables
- **Qualify Clauses**: Deduplication at query time

### Data Lineage Complexity

The pipeline demonstrates several advanced lineage patterns:

1. **Multi-source Joins**: DEX_TRADES_STABLE combines raw events with metadata
2. **Dynamic Dependencies**: COIN_INFO updates affect downstream views
3. **Complex Views**: FILTERED_DEX_TRADES_VIEW has non-obvious dependencies
4. **Cross-database References**: BTC analysis references external price data

## Usage Patterns for igloo-mcp

### Catalog Generation
```bash
# Full database catalog
Use MCP client to catalog --database DEFI_SAMPLE_DB

# Schema-specific catalog
Use MCP client to catalog --database DEFI_SAMPLE_DB --schema ANALYTICS
```

### Lineage Analysis
```bash
# Main fact table lineage (shows complex dependencies)
Use MCP client to lineage DEX_TRADES_STABLE --direction both --depth 3

# Filtered view lineage (demonstrates view dependencies)
Use MCP client to lineage FILTERED_DEX_TRADES_VIEW --direction upstream

# BTC analytics lineage (shows dynamic table refresh chain)
Use MCP client to lineage BTC_DEX_TRADES_USD_DT --direction upstream
```

### Dependency Graphs
```bash
# Visualize full pipeline dependencies
Use MCP client to depgraph --database DEFI_SAMPLE_DB --format dot

# Generate JSON for custom visualization
Use MCP client to depgraph --database DEFI_SAMPLE_DB --format json
```

## MCP Integration Examples

### Natural Language Queries
- **"Show me the schema of the main trading table"** → DEX_TRADES_STABLE structure
- **"What feeds into the BTC analytics?"** → Upstream lineage analysis
- **"How many trades happened yesterday by protocol?"** → Aggregation query
- **"Build a catalog for the DeFi database"** → Full metadata extraction

### Advanced Analytics Questions
- **"What's the lineage for filtered trades view?"** → Complex view dependencies
- **"Show me the dependency graph for BTC analytics"** → Dynamic table refresh chain
- **"Which tables depend on coin metadata?"** → Downstream impact analysis
- **"How does the pipeline handle real-time updates?"** → Dynamic table explanation

## Business Value

This pipeline enables several high-value use cases:

1. **Trading Analytics**: Volume, frequency, and user behavior analysis
2. **Token Discovery**: Identify trending cryptocurrencies
3. **Liquidity Analysis**: Pool performance and efficiency metrics
4. **User Segmentation**: Classify traders by behavior patterns
5. **Protocol Comparison**: Cross-DEX performance analysis
6. **Data Quality**: Filter genuine trades from routing activity

## Technical Innovations

### 1. User-Initiated Trade Detection
The FILTERED_DEX_TRADES_VIEW implements sophisticated logic to distinguish between:
- **Direct user trades**: User wallet → DEX swap
- **Routing trades**: Intermediate swaps in multi-hop routes
- **Arbitrage activity**: Bot-driven trading

### 2. Dynamic Metadata Management
The COIN_INFO dynamic table automatically:
- Discovers new tokens from blockchain events
- Updates metadata when tokens change
- Maintains historical versions for analysis

### 3. Multi-Protocol Normalization
The pipeline handles differences across DEX protocols:
- Standardized token identifiers
- Consistent trade direction logic (A_TO_B)
- Protocol-specific pool naming conventions

This real-world pipeline demonstrates the complexity and business value that igloo-mcp can help analyze and understand through automated cataloging, lineage analysis, and dependency mapping.
