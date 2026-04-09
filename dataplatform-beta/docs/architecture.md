# Architecture

## Overview
Dataplatform-beta is an Azure Databricks platform with a batch-first operating model, optional streaming by exception, and Power BI delivery from curated Gold marts.

## Core Components
- Azure Databricks workspaces per environment (dev/test/prod).
- ADLS Gen2 storage accounts per environment.
- Unity Catalog for governance and data access control.
- Event Hubs for approved low-latency use cases.
- Power BI workspaces and deployment pipeline for report delivery.

## Data Flow
1. Sources land in Raw.
2. Bronze standardizes and validates ingestion.
3. Silver conforms data to domain contracts.
4. Gold publishes serving marts for semantic models.
5. Power BI semantic models and thin reports consume Gold.

See diagrams in docs/architecture-flow-diagrams.md.
