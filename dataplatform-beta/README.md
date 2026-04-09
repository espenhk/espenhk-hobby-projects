# dataplatform-beta

Azure Databricks data platform scaffold with PBIP-first Power BI delivery, CI/CD workflows, and Terraform foundations.

## What is implemented
- Planning baseline: architecture, security, operations, and 90-day roadmap.
- PBIP repository structure for semantic models and reports.
- Deployment config contracts for workspaces and pipeline rules.
- GitHub Actions workflows for PBIP validation and release orchestration.
- GitHub Actions workflows for Terraform fmt/init/validate and data-contract checks.
- Python utility scripts for PBIP validation, smoke checks, and deployment pipeline promotion.
- Python utility script for data-contract validation.
- Terraform module scaffold for Entra groups used by Power BI RBAC.
- Initial dataset contract scaffolding under databricks/contracts.

## Directory map
- PLAN.md: platform plan and decisions.
- docs/architecture.md: architecture overview and component responsibilities.
- docs/security-compliance.md: baseline security/compliance controls.
- docs/operations-slos.md: SLI/SLO and alerting baseline.
- docs/powerbi-serving.md: Power BI delivery operating model.
- powerbi/deployment/: workspace and pipeline config maps.
- powerbi/domains/: domain PBIP artifacts.
- ci/: GitHub Actions workflows for Power BI, Terraform, and data contracts.
- scripts/powerbi/: Power BI automation helpers used by workflows.
- scripts/contracts/: data-contract validation helpers.
- databricks/contracts/: versioned data contracts for CI enforcement.
- terraform/: IaC scaffold for Power BI RBAC groups.

## GitHub configuration required
Repository variables:
- PBI_PIPELINE_ID
- PBI_DEV_WORKSPACE_ID
- PBI_TEST_WORKSPACE_ID
- PBI_PROD_WORKSPACE_ID
- PBI_DEV_DATASET_ID
- PBI_TEST_DATASET_ID
- PBI_PROD_DATASET_ID
- PBI_DEV_REPORT_ID
- PBI_TEST_REPORT_ID
- PBI_PROD_REPORT_ID

Repository secrets:
- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID

## Workflow behavior
- ci/powerbi-pr-validation.yml:
  - Runs PBIP structural and naming checks on pull requests.
- ci/powerbi-release.yml:
  - Push to main: validates PBIP conventions, updates Dev, runs Dev smoke checks, promotes Dev -> Test.
  - Manual workflow dispatch on main: promotes Test -> Prod with change ticket gate.
  - Runs post-promotion smoke checks.
- ci/terraform-validate-plan.yml:
  - Runs terraform fmt -check and terraform init/validate for all dev/test/prod stack roots on pull requests.
- ci/data-contract-checks.yml:
  - Runs data-contract JSON validation on pull requests touching contract files.

## Local validation
Run PBIP validation:

python dataplatform-beta/scripts/powerbi/validate_pbip.py

Run data-contract validation:

python dataplatform-beta/scripts/contracts/validate_contracts.py

## Architecture and flow diagrams
Mermaid source diagrams are in docs/architecture-flow-diagrams.md and embedded here for quick review.

### Platform architecture

```mermaid
flowchart LR
  subgraph Sources[Source Systems]
    S1[Operational DBs]
    S2[SaaS APIs]
    S3[Files and Events]
  end

  subgraph Azure[Azure Platform]
    EH[Event Hubs]
    AL[Databricks Auto Loader]
    DBX[Azure Databricks]
    UC[Unity Catalog]
    ADLS[ADLS Gen2 Delta Lake]
    KV[Key Vault]
    LA[Log Analytics and Alerts]
    ENTRA[Entra ID Groups]
  end

  subgraph BI[Power BI]
    WS[Dev/Test/Prod Workspaces]
    PIPE[Deployment Pipeline Dev -> Test -> Prod]
    USERS[Business Consumers]
  end

  S1 --> AL
  S2 --> AL
  S3 --> EH
  EH --> DBX
  AL --> DBX
  DBX <--> ADLS
  UC -. governance .- DBX
  KV -. secrets .- DBX
  ENTRA -. RBAC .- UC
  DBX --> WS
  WS --> PIPE
  PIPE --> USERS
  DBX --> LA
  WS --> LA
```

### Data flow

```mermaid
flowchart LR
  SRC[Batch Files and Event Streams] --> RAW[Raw Immutable Landing]
  RAW --> BRONZE[Bronze Standardized Delta]
  BRONZE --> SILVER[Silver Validated and Conformed]
  SILVER --> GOLD[Gold Star Schemas and Data Marts]

  BRONZE --> Q[Quarantine Invalid Records + Reason Codes]
  SILVER --> Q

  ORCH[Databricks Workflows] -. orchestrates .-> BRONZE
  ORCH -. orchestrates .-> SILVER
  ORCH -. orchestrates .-> GOLD

  GOLD --> SM[PBIP Semantic Models]
  SM --> RPT[Thin Reports]
  RPT --> CON[Business Consumers]
```

### CI/CD flow

```mermaid
flowchart TD
  DEV[Developer Change] --> PR[Pull Request]

  PR --> PBIP_CI[CI powerbi-pr-validation]
  PBIP_CI --> MERGE[Merge to main]
  MERGE --> DEV_RUN[Release workflow publish or sync to Dev]
  DEV_RUN --> DEV_SMOKE[Dev smoke checks]
  DEV_SMOKE --> TEST_PROMOTE[Promote Dev -> Test]
  TEST_PROMOTE --> TEST_SMOKE[Test smoke checks]
  TEST_SMOKE --> PROD_GATE[Manual dispatch + change ticket]
  PROD_GATE --> PROD_PROMOTE[Promote Test -> Prod]
  PROD_PROMOTE --> PROD_SMOKE[Prod smoke checks]
```

## Terraform bootstrap (Power BI RBAC)

cd dataplatform-beta/terraform/environments/dev/powerbi_rbac
terraform init
terraform plan -var-file=terraform.tfvars.example

## Next implementation steps
1. Add tenant-specific PBIP publish-to-Dev mechanism before smoke checks.
2. Replace static IDs with dynamic mapping lookup from deployment config.
3. Add richer semantic model static checks in PR validation.
4. Extend Terraform environments for test/prod and provider wiring.
