# Terraform Scaffold

Single deployment root (`deployment/`) wiring reusable modules for the platform baseline. Environments (`dev`/`test`/`prod`) are selected with Terraform workspaces and tfvars, not per-environment stack folders.

## Modules
- modules/network: VNet, subnets, NSGs, private DNS zones, private endpoints
- modules/storage: ADLS Gen2 storage account and filesystems
- modules/key_vault: Key Vault baseline
- modules/databricks: VNet-injected Databricks workspace
- modules/unity_catalog: storage credential and external location
- modules/foundry: Azure AI Foundry (ML workspace) and App Insights
- modules/monitor_alerting: Log Analytics, saved searches, action group, metric alerts
- modules/budget: resource group budgets
- modules/powerbi: Entra groups for Power BI RBAC
- modules/landing_zone: placeholder

## Usage
1. Copy `deployment/backend.hcl.example` and `deployment/terraform.tfvars.example` and fill them in.
2. From `deployment/`, run `terraform init -backend-config=backend.hcl`, then plan/apply.
3. Databricks workspace-level resources (Unity Catalog) need a second apply once the workspace exists; see `deployment/terraform.tfvars.example`.

## Outputs
See `deployment/outputs.tf`. The Power BI group outputs should be used to bind workspace roles and deployment pipeline permissions.
