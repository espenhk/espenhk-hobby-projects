# Security and Compliance Baseline

## Security Defaults
- Private endpoints for ADLS Blob/DFS and Key Vault access paths, implemented in the network module.
- Public network access disabled by default for supported PaaS resources.
- Default-deny outbound network policy with explicit allowlists.
- Entra group-based RBAC and least-privilege permissions.

## Secrets and Identity
- Managed identity preferred for automation where possible.
- Service principals allowed only when required and documented.
- Key Vault used for exception secrets and the Foundry-to-Databricks connection contract.
- Foundry receives read/list secret permissions only.
- Databricks exchange publishing uses the Databricks access connector managed identity.

Connection contract secrets:
- `foundry-databricks-connection-contract`: JSON metadata with Databricks host, workspace resource ID, Unity Catalog catalog/schema, external location name, external location URL, and PAT secret reference.
- `foundry-databricks-pat`: optional PAT secret for Foundry connectivity when managed identity is not sufficient.

## Logging and Audit
- Diagnostic logs centralized to Log Analytics.
- Recommended Log Analytics saved searches cover storage availability, Key Vault failures, and Databricks error signals.
- Access, deployment, and privilege-change events retained for audit.

## Compliance Controls (Engineering)
- Dataset classification, ownership, and retention tags.
- DSR runbook scaffolding for access/correction/deletion flows.
- Change trail for production releases and approvals.

## Open Compliance Decisions
- Approved Azure regions and residency boundaries.
- Compliance ownership model for DSR and policy exceptions.
