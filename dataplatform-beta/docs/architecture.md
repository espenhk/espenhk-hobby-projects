# Architecture

## Overview
Dataplatform-beta is an Azure Databricks platform with a batch-first operating model, optional streaming by exception, Azure AI Foundry integration for approved exchange outputs, and Power BI delivery from curated Gold marts.

## Core Components
- Azure Databricks workspaces per environment (dev/test/prod).
- Azure AI Foundry workspace per environment for governed AI access patterns.
- ADLS Gen2 storage accounts per environment.
- Unity Catalog for governance, external locations, and data access control.
- Log Analytics workspace and Azure Monitor alerting per environment.
- Key Vault connection contract for Foundry to Databricks connectivity metadata.
- Event Hubs for approved low-latency use cases.
- Power BI workspaces and deployment pipeline for report delivery.

## Data Flow
1. Sources land in Raw.
2. Bronze standardizes and validates ingestion.
3. Silver conforms data to domain contracts.
4. Gold publishes serving marts for semantic models and approved extracts for `foundry-exchange`.
5. Unity Catalog external locations expose approved exchange paths to Databricks workloads.
6. Foundry reads the Key Vault connection contract and approved exchange outputs.
7. Power BI semantic models and thin reports consume Gold.

Example implementation note:
- The `core_nordic_sales_nok` sample is split into dedicated raw, bronze, silver, and gold Python modules and orchestrated through a Databricks Asset Bundle job definition.

See diagrams in docs/architecture-flow-diagrams.md.
