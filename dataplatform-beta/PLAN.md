# Dataplatform Beta Plan

## Goal
Build a Terraform-defined Azure Databricks data platform that is batch-first, contract-driven, and optimized to serve trusted, governed data to Power BI.

## How to Use This Plan
- Read sections in order: scope -> architecture decisions -> roadmap -> backlog.
- Treat "Phase 1 Decisions Locked" as non-negotiable unless explicitly changed by architecture review.
- Treat "Remaining Open Decisions" as blockers to resolve before production go-live.
- Use the 90-day roadmap as milestone planning and the backlog as sprint-level intake.

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
- Use separate ADLS Gen2 storage accounts per environment.
- Use group-based access via Entra ID; avoid direct user grants on data objects.

### Provider Strategy
- Pin Terraform providers with bounded versions and commit lock files in environment roots.
- Use explicit provider aliases for split planes:
  - azurerm for Azure resources.
  - azuread for Entra groups and identities.
  - databricks.account for account-level resources.
  - databricks.workspace for workspace-level resources.
- Configure providers in root environment stacks and pass providers explicitly to modules.

### Data Design
- Use Delta Lake and medallion layers: Raw -> Bronze -> Silver -> Gold.
- Keep Raw immutable and auditable.
- Apply explicit schema and data contracts in Silver and Gold.
- Route invalid records to Quarantine with reason codes.

### Ingestion
- Batch default:
  - Auto Loader for file increments.
  - Databricks Workflows scheduled runs.
- Streaming exception path:
  - Use Event Hubs (or Kafka-compatible) + Structured Streaming micro-batch only when batch cannot meet SLA.
  - Streaming requires explicit justification: latency target, event volume, checkpoint/recovery design, and named operational owner.

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
  - Workspace (Phase 1 core): pbi-dpb-<env>-core

Phase 2 note:
- Additional domain-specific workspaces are allowed only after architecture review.

Decision rule:

| Condition | Recommended mode | Notes |
|---|---|---|
| SLA > 60 minutes | Import | Default mode for reliability and cost control. |
| SLA 5-60 minutes | DirectQuery (pilot) | Require benchmark gate pass for latency, concurrency, and cost. |
| SLA < 5 minutes | Architecture exception review | Do not implement by default in phase 1. |
| Fabric-first strategy + large semantic models | Direct Lake | Use only when OneLake/Fabric is an explicit strategic standard. |

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
- One workflow task per target table across Bronze, Silver, and Gold.
- Favor incremental processing for Silver/Gold by default.
- Allow overwrite only for bounded snapshots or deterministic rebuilds.
- Allow MERGE only with explicit written justification, key guarantees, and automated tests.
- Keep transformation logic pure (DataFrame in -> DataFrame out).

### Streaming Runtime Standards (minimum)
- Mandatory checkpoint location per stream, isolated by environment and pipeline.
- Explicit watermark and late-arrival policy per event type.
- Idempotent write strategy for retries and replay.
- Replay runbook with source boundary, backfill window, and post-run validation checks.

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
- CD pipeline (current state):
  - Push to main: publish or sync PBIP artifacts to Dev (tenant-specific), then run smoke validation.
  - Push to main: promote Dev -> Test with approval gates.
  - workflow_dispatch on main only: promote Test -> Prod with change ticket and approval gates.
  - Block promotion if refresh/validation gates fail.
- Release governance:
  - Require change ticket reference for Prod promotions.
  - Require main branch protection and required checks.
  - Require GitHub environment approvals for Test and Prod promotions.
  - Persist deployment logs/artifacts for audit.

## Azure Security and Compliance Baseline
- Enforce hub-spoke networking with private endpoints for ADLS, Key Vault, Event Hubs, Databricks, and monitoring paths.
- Disable public network access on supported PaaS resources by default; exceptions require risk acceptance with expiry.
- Enforce default-deny outbound controls with explicit allowlists.
- Use Key Vault-backed secret management.
- Enable diagnostic logs to central Log Analytics with defined retention.

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

SLI measurement policy (phase 1):
- Batch availability SLI: successful scheduled runs / total scheduled runs (excluding approved maintenance windows).
- Freshness SLI: on-time Gold table updates within contracted window.
- Power BI refresh SLI: successful refreshes completed within target duration.
- Streaming lag SLI: monitored minutes under lag threshold / total monitored minutes.

Alert catalog minimum fields:
- Trigger query and threshold.
- Severity and duration.
- Owner and escalation path.
- Runbook URL.
- Dedupe/suppression policy.

## Terraform-First Repository Structure (target state)

State model:
- One state key per environment stack using <env>/<stack>.tfstate naming.
- Stack split per environment: foundation, connectivity, security, data_platform, governance, observability, powerbi.
- Locking required for all plan/apply operations.
- Do not read remote state directly from modules; pass dependencies through root outputs and CI inputs.

```text
dataplatform-beta/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── security-compliance.md
│   ├── operations-slos.md
│   └── powerbi-serving.md
├── powerbi/
│   ├── domains/
│   │   └── core/
│   │       ├── semantic-model/
│   │       └── reports/
│   └── deployment/
│       ├── workspace-map.yaml
│       └── pipeline-rules.yaml
├── terraform/
│   ├── modules/
│   │   ├── landing_zone/
│   │   ├── network/
│   │   ├── databricks/
│   │   ├── unity_catalog/
│   │   ├── storage/
│   │   ├── key_vault/
│   │   ├── monitor_alerting/
│   │   ├── budget/
│   │   ├── foundry/
│   │   └── powerbi/
│   └── environments/
│       ├── dev/
│       ├── test/
│       └── prod/
├── databricks/
│   ├── jobs/
│   ├── pipelines/
│   ├── contracts/
│   └── sql/
└── ci/
    ├── terraform-validate-plan.yml
    ├── data-contract-checks.yml
    ├── powerbi-pr-validation.yml
    └── powerbi-release.yml
```

## 90-Day Roadmap

### Days 0-30
- Establish Terraform landing zone and environment scaffolding.
- Provision Databricks + storage + Unity Catalog + RBAC baseline in dev/test/prod; keep prod workloads disabled until readiness gates pass.
- Build first end-to-end batch pipeline to one Gold mart.
- Create first PBIP semantic model and thin report from Gold.
- Stand up pbi-dpb-dev-core, pbi-dpb-test-core, and pbi-dpb-prod-core workspaces.
- Configure dpb-core-bi deployment pipeline and initial deployment rules.
- Stand up baseline dashboards and P1/P2 alerts.

Exit criteria:
- Terraform plan/apply succeeds in dev and test with no manual post-steps.
- One Gold mart feeds one PBIP semantic model and one thin report in Dev.
- P1/P2 alert routes are tested and acknowledged by on-call owner.

### Days 31-60
- Expand to 2-4 domains with reusable ingestion/transformation templates.
- Enforce contract checks in CI and pre-deploy gates.
- Add quarantine and quality score reporting.
- Harden cluster policies, cost guardrails, and access recertification workflow.
- Add PBIP PR validation workflow and automatic publish to Dev on merge.
- Add Test promotion gate with UAT approval and refresh smoke tests.

Exit criteria:
- At least 2 domains use shared ingestion/transformation templates.
- Contract checks block merges on schema/contract violations.
- Test promotion requires explicit UAT approval and passing refresh smoke tests.

### Days 61-90
- Evaluate one candidate near-real-time use case and implement streaming only if batch cannot meet SLA.
- Pilot DirectQuery for one near-real-time Power BI use case.
- Run DR tabletop and one restore simulation.
- Finalize production readiness checklist and incident runbooks.
- Add Prod promotion gate with auditable approval and rollback checklist.

Exit criteria:
- Streaming pipeline meets agreed freshness target for pilot dataset.
- DirectQuery pilot passes performance thresholds and stakeholder acceptance.
- DR restore simulation and production readiness checklist are signed off.

## Initial Backlog (Execution-Ready)
Execution note:
- For each backlog item, assign owner, target sprint, and acceptance criteria before implementation starts.

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
5. Dataset tiering criteria (Tier-1/Tier-2) and associated SLO targets.
6. Data quality enforcement thresholds (block vs quarantine) and exception authority.
7. Support operating model (hours, on-call ownership, escalation).

## Agent Review Reconciliation (April 2026)
Resolved in this revision:
- Clarified workspace naming and phase-2 expansion rule.
- Clarified CI/CD release policy and manual prod promotion expectations.
- Converted streaming from implied default to explicit exception path.
- Strengthened security baseline to default-private/default-deny posture.
- Added SLI definitions and minimum alert-catalog requirements.
- Added Terraform provider and state-model execution guidance.

Still to finalize:
- Tier-1 domain selection and SLO values.
- Regional residency and compliance ownership approvals.

## Definition of Done for Planning Phase
- Architecture, security, and operations choices documented and approved.
- Terraform module boundaries agreed.
- First 90-day milestones approved with owners.
- SLA targets for first Tier-1 data products agreed.
- Execution backlog prioritized for sprint 1.
- PBIP repository standards, workspace model, and release pipeline approved.
