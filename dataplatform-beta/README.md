# dataplatform-beta

Azure Databricks data platform scaffold with PBIP-first Power BI delivery, CI/CD workflows, and Terraform foundations.

## What is implemented
- Planning baseline: architecture, security, operations, and 90-day roadmap.
- PBIP repository structure for semantic models and reports.
- Deployment config contracts for workspaces and pipeline rules.
- GitHub Actions workflows for PBIP validation and release orchestration.
- Python utility scripts for PBIP validation, smoke checks, and deployment pipeline promotion.
- Terraform module scaffold for Entra groups used by Power BI RBAC.

## Directory map
- PLAN.md: platform plan and decisions.
- docs/powerbi-serving.md: Power BI delivery operating model.
- powerbi/deployment/: workspace and pipeline config maps.
- powerbi/domains/: domain PBIP artifacts.
- ci/: GitHub Actions workflows for Power BI.
- scripts/powerbi/: automation helpers used by workflows.
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
  - Validates PBIP conventions on main.
  - Runs smoke checks in Dev.
  - Promotes Test and Prod using Power BI deployment pipeline API.
  - Runs post-promotion smoke checks.

## Local validation
Run PBIP validation:

python dataplatform-beta/scripts/powerbi/validate_pbip.py

## Terraform bootstrap (Power BI RBAC)

cd dataplatform-beta/terraform/environments/dev
terraform init
terraform plan -var-file=terraform.tfvars.example

## Next implementation steps
1. Add tenant-specific PBIP publish-to-Dev mechanism before smoke checks.
2. Replace static IDs with dynamic mapping lookup from deployment config.
3. Add richer semantic model static checks in PR validation.
4. Extend Terraform environments for test/prod and provider wiring.
