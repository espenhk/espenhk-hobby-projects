# Dataplatform Beta Plan

## Goal
Build a Terraform-defined Azure Databricks data platform that supports batch and streaming data and is optimized to serve trusted, governed data to Power BI.

## Product Scope (Phase 1)
- Provision a repeatable Azure + Databricks foundation across dev, test, and prod.
- Support both batch and streaming ingestion into a Delta medallion model.
- Deliver curated Gold marts for Power BI with clear SLA and ownership.
- Enforce baseline security, governance, observability, and cost controls.

Out of scope in phase 1:
- Multi-region active-active architecture.
- Full enterprise governance operating model rollout.
- Broad self-service BI enablement without guardrails.

## Architecture Decisions

### Platform and Governance
- Use Unity Catalog from day 1 for governance, lineage, and access control.
- Use one Databricks workspace per environment (dev/test/prod).
- Use separate ADLS Gen2 storage accounts (or strongly isolated containers) per environment.
- Use group-based access via Entra ID; avoid direct user grants on data objects.

### Data Design
- Use Delta Lake and medallion layers: Raw -> Bronze -> Silver -> Gold.
- Keep Raw immutable and auditable.
- Apply explicit schema and data contracts in Silver and Gold.
- Route invalid records to Quarantine with reason codes.

### Ingestion
- Batch default:
  - Auto Loader for file increments.
  - Databricks Workflows scheduled runs.
- Streaming targeted:
  - Event Hubs (or Kafka-compatible) + Structured Streaming micro-batch.
  - Start with one high-value near-real-time use case in first 90 days.

### Serving to Power BI (default strategy)
- Primary mode: Import from curated Gold star schemas.
- Add DirectQuery only for near-real-time dashboards with strict SLA needs.
- Consider Direct Lake later if Fabric/OneLake becomes a strategic standard.

### Power BI Delivery Model (PBIP-first decisions)
- Use PBIP as the source-of-truth format for semantic models and reports in this repository.
- Keep one semantic model per business domain and favor thin reports that reference shared semantic models.
- Store environment-specific connection settings as deploy-time parameters, not hardcoded in PBIP files.
- Manage all deployment through CI/CD and Power BI Deployment Pipelines; no manual report publishing to Test/Prod.
- Use service principal authentication for CI/CD publishing and deployment.
- Require pull-request review for all PBIP changes, including semantic model measures and report visuals.
- Adopt a strict naming standard:
  - Semantic model: sm_<domain>_<subject>
  - Report: rpt_<domain>_<audience>_<purpose>
  - Workspace: pbi-dpb-<env>-<domain>

Decision rule:
- SLA >= 1 hour: Import.
- SLA 5-60 minutes: DirectQuery pilot.
- Fabric-first strategy + large semantic models: Direct Lake.

### Power BI Workspaces and Deployment Pipelines (phase 1 design)
- Workspaces:
  - pbi-dpb-dev-core: development workspace for data platform owned reports/models.
  - pbi-dpb-test-core: UAT and validation workspace.
  - pbi-dpb-prod-core: production workspace.
- Deployment pipeline:
  - dpb-core-bi with stages Dev -> Test -> Prod.
- Rules and controls:
  - Deploy only from pipeline promotion, not direct publish to Test/Prod.
  - Use deployment rules for environment bindings (data source, parameter values, refresh settings).
  - Restrict Build permissions in Prod to approved Entra groups.
  - Enforce certified/endorsed semantic models before broad report reuse.
- Capacity model:
  - Non-prod (Dev/Test): shared capacity.
  - Prod: dedicated capacity for isolation and SLA control.

### Pipeline Patterns
- One workflow task per target Silver/Gold table.
- Favor overwrite for Silver/Gold by default.
- Allow MERGE only with explicit key guarantees and tests.
- Keep transformation logic pure (DataFrame in -> DataFrame out).

### Power BI CI/CD Integration (GitHub + Azure)
- Repository model:
  - Keep PBIP artifacts in source control under a dedicated powerbi directory.
  - Separate semantic model and report folders by domain.
- Authentication and secrets:
  - Use OIDC federation from GitHub Actions to Azure.
  - Use Entra app/service principal with least privilege to Power BI and workspace scopes.
  - Store non-federated secrets only in Azure Key Vault when unavoidable.
- CI pipeline (pull requests):
  - Validate PBIP file structure and metadata consistency.
  - Run semantic model checks (naming, measure formatting, banned patterns).
  - Run optional static checks for report references to missing fields/measures.
- CD pipeline (merge to main and release tags):
  - Publish PBIP artifacts to Dev workspace.
  - Run smoke validation (dataset refresh trigger, report open check, key visual query checks).
  - Promote Dev -> Test -> Prod through deployment pipeline with approvals.
  - Block Prod promotion if refresh/validation gates fail.
- Release governance:
  - Require change ticket reference for Prod promotions.
  - Persist deployment logs/artifacts for audit.

## Azure Security and Compliance Baseline
- Hub-spoke networking with private endpoints for ADLS, Key Vault, Event Hubs, and monitoring paths.
- Databricks secure networking posture (no public compute IPs where supported).
- Enforce outbound controls and approved egress paths.
- Use Key Vault-backed secret management.
- Enable diagnostic logs to central Log Analytics.

Compliance-ready controls (engineering baseline):
- Data classification tags, owner tags, purpose tags, retention class tags.
- Retention and deletion runbook scaffolding for data subject rights workflows.
- Audit trail coverage for data access, role changes, and platform changes.
- AI governance readiness: use-case registry, lineage, and change traceability.

## Operations and Reliability Baseline
- Monitoring domains:
  - Pipeline success/failure and duration.
  - Streaming lag and restart frequency.
  - Data freshness by Gold table.
  - Power BI refresh reliability and latency.
  - Cost by domain/workload.
- Alerting:
  - P1: critical SLA misses, stopped Tier-1 streams, repeated Power BI refresh failures.
  - P2: elevated failure rates, lag growth, dependency degradation.
- SLOs (initial):
  - Tier-1 batch availability: 99.5% monthly.
  - Tier-1 freshness compliance: 99.0% monthly.
  - Tier-1 Power BI refresh within SLA: 99.0% monthly.

## Terraform-First Repository Structure (proposed)

dataplatform-beta/
- README.md
- docs/
  - architecture.md
  - security-compliance.md
  - operations-slos.md
  - powerbi-serving.md
- powerbi/
  - domains/
    - core/
      - semantic-model/
      - reports/
  - deployment/
    - workspace-map.yaml
    - pipeline-rules.yaml
- terraform/
  - modules/
    - landing_zone/
    - network/
    - databricks_workspace/
    - unity_catalog/
    - storage/
    - private_endpoints/
    - key_vault/
    - monitor_alerting/
    - budgets_tags_policy/
  - environments/
    - dev/
    - test/
    - prod/
- databricks/
  - jobs/
  - pipelines/
  - contracts/
  - sql/
- ci/
  - terraform-validate-plan.yml
  - data-contract-checks.yml
  - powerbi-pr-validation.yml
  - powerbi-release.yml

## 90-Day Roadmap

### Days 0-30
- Establish Terraform landing zone and environment scaffolding.
- Provision Databricks + storage + Unity Catalog + RBAC baseline in dev/test.
- Build first end-to-end batch pipeline to one Gold mart.
- Create first PBIP semantic model and thin report from Gold.
- Stand up pbi-dpb-dev-core, pbi-dpb-test-core, and pbi-dpb-prod-core workspaces.
- Configure dpb-core-bi deployment pipeline and initial deployment rules.
- Stand up baseline dashboards and P1/P2 alerts.

### Days 31-60
- Expand to 2-4 domains with reusable ingestion/transformation templates.
- Enforce contract checks in CI and pre-deploy gates.
- Add quarantine and quality score reporting.
- Harden cluster policies, cost guardrails, and access recertification workflow.
- Add PBIP PR validation workflow and automatic publish to Dev on merge.
- Add Test promotion gate with UAT approval and refresh smoke tests.

### Days 61-90
- Add one focused streaming use case from ingest to Gold.
- Pilot DirectQuery for one near-real-time Power BI use case.
- Run DR tabletop and one restore simulation.
- Finalize production readiness checklist and incident runbooks.
- Add Prod promotion gate with auditable approval and rollback checklist.

## Initial Backlog (Execution-Ready)
1. Bootstrap Terraform backend/state with locking and RBAC.
2. Implement naming/tag standards and policy-as-code baseline.
3. Deploy networking module with private connectivity pattern.
4. Deploy Databricks workspace module and cluster policies.
5. Configure Unity Catalog, external locations, and role model.
6. Create medallion schema and contract templates.
7. Implement first batch ingestion + Silver/Gold transforms.
8. Create Power BI-ready star schema in Gold.
9. Add monitor/alert modules and operations dashboard.
10. Add CI gates: fmt/validate/plan + contract tests.
11. Add PBIP folder conventions and semantic model/report naming lint checks.
12. Implement powerbi-pr-validation workflow.
13. Implement powerbi-release workflow for Dev publish and staged promotion.
14. Configure Power BI deployment pipeline rules for Dev/Test/Prod bindings.
15. Define Power BI workspace RBAC groups and ownership model.

## Phase 1 Decisions Locked
1. Environments: dev/test/prod all provisioned from the start; prod go-live controlled by readiness gates.
2. Power BI source control format: PBIP only for all new reports and semantic models.
3. Workspace topology: one workspace per environment for core platform-owned BI assets.
4. Deployment path: mandatory Dev -> Test -> Prod through deployment pipeline.
5. Ownership model: platform team owns shared semantic models; domain teams own thin reports with review gates.
6. Capacity model: shared non-prod capacity and dedicated prod capacity.

## Remaining Open Decisions
1. Regional residency constraints and approved Azure regions.
2. First domain and first Tier-1 dataset for SLA commitment.
3. Final service-level targets for first production Power BI domain.
4. Identity and admin operating model boundary between platform and shared cloud ops.

## Definition of Done for Planning Phase
- Architecture, security, and operations choices documented and approved.
- Terraform module boundaries agreed.
- First 90-day milestones approved with owners.
- SLA targets for first Tier-1 data products agreed.
- Execution backlog prioritized for sprint 1.
- PBIP repository standards, workspace model, and release pipeline approved.
