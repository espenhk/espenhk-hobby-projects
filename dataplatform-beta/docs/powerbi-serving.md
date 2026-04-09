# Power BI Serving Design (PBIP-First)

## Purpose
Define how Power BI semantic models and reports are versioned, validated, deployed, and operated from this repository.

## Scope
- PBIP source control standards.
- Workspace topology and deployment pipeline.
- CI/CD flow and release controls.
- RBAC model and ownership boundaries.

## PBIP Standards
- All new semantic models and reports must be created and committed as PBIP artifacts.
- Shared semantic models are domain-scoped and reused by thin reports.
- Environment-specific settings must be parameterized and injected at deployment time.
- Direct edits in Test/Prod workspaces are not allowed.

## Repository Layout
- powerbi/domains/<domain>/semantic-model/
- powerbi/domains/<domain>/reports/<report_name>/
- powerbi/deployment/workspace-map.yaml
- powerbi/deployment/pipeline-rules.yaml

## Naming Convention
- Semantic model: sm_<domain>_<subject>
- Report: rpt_<domain>_<audience>_<purpose>
- Workspace: pbi-dpb-<env>-<domain>
- Deployment pipeline: dpb-<domain>-bi

## Workspace Topology (Phase 1)
- pbi-dpb-dev-core
- pbi-dpb-test-core
- pbi-dpb-prod-core

Guidelines:
- Dev: model/report authoring and integration testing.
- Test: UAT and release candidate validation.
- Prod: governed publish target for consumers.

## Deployment Pipeline
- Pipeline name: dpb-core-bi
- Stages: Dev -> Test -> Prod
- Promotions:
  - Dev -> Test: requires CI green and reviewer approval.
  - Test -> Prod: requires UAT sign-off, change ticket, and smoke check pass.

## Data Connectivity
- Default serving mode: Import from Databricks Gold schemas.
- Pilot mode: DirectQuery for low-latency needs.
- Connection details are bound by environment rules from deployment config files.

## CI/CD Flow
1. Pull request validation
- Validate PBIP artifact structure.
- Validate naming convention and ownership metadata.
- Validate semantic model references and required objects.

2. Main branch deployment
- Publish PBIP artifacts to Dev workspace.
- Trigger refresh for impacted semantic models.
- Run smoke checks (dataset refresh status, report render checks).

3. Promotion
- Promote via deployment pipeline to Test then Prod.
- Apply deployment rule overrides per environment.
- Record deployment evidence (run ID, approver, timestamp).

## GitHub CI/CD Configuration Contract
Required repository variables:
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

Required manual input for production promotion:
- change_ticket (workflow dispatch input, format CHG-<digits> or RFC-<digits>)

Required repository secrets:
- AZURE_CLIENT_ID
- AZURE_TENANT_ID
- AZURE_SUBSCRIPTION_ID

Workflow/script mapping:
- PR validation workflow calls scripts/powerbi/validate_pbip.py.
- Release workflow calls scripts/powerbi/smoke_check.py for each stage.
- Release workflow calls scripts/powerbi/pipeline_promote.py for Test/Prod promotions.

Implementation note:
- Publish-to-Dev is modeled as validation + smoke check in the current workflow, then stage promotions move artifacts through the deployment pipeline.
- If your tenant uses Git-connected workspace sync as publish, add a dedicated sync step before Dev smoke checks.

## RBAC and Ownership
Groups (Entra ID):
- grp-pbi-core-admins: pipeline/workspace admin rights.
- grp-pbi-core-developers: Dev authoring and publish rights.
- grp-pbi-core-testers: Test validation rights.
- grp-pbi-core-consumers: Prod read and app access.

Ownership:
- Platform team owns shared semantic models.
- Domain teams own thin reports, with mandatory review for shared-model changes.

## Release Gates
- Required PR approvals for semantic model changes.
- Required CI pass for PBIP checks.
- Required smoke test pass before promotion.
- Required approval for Prod promotion.

## Rollback
- Keep previous successful artifact version for each promoted stage.
- Roll back by redeploying prior artifact version through the deployment pipeline.
- Log all rollback actions with reason and impacted assets.

## Operational Metrics
- Dataset refresh success rate.
- Refresh duration against SLA.
- Report open/render failure rate.
- Deployment success/failure by stage.

## Near-Term Implementation Checklist
1. Establish workspace and pipeline objects.
2. Enable service principal access and minimum required permissions.
3. Commit first domain semantic model and thin report as PBIP.
4. Enable PR validation and release workflows.
5. Run first end-to-end deployment and rollback drill.
