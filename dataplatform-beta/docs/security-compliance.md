# Security and Compliance Baseline

## Security Defaults
- Private endpoints for ADLS, Key Vault, Event Hubs, and Databricks access paths.
- Public network access disabled by default for supported PaaS resources.
- Default-deny outbound network policy with explicit allowlists.
- Entra group-based RBAC and least-privilege permissions.

## Secrets and Identity
- Managed identity preferred for automation where possible.
- Service principals allowed only when required and documented.
- Key Vault used for exception secrets.

## Logging and Audit
- Diagnostic logs centralized to Log Analytics.
- Access, deployment, and privilege-change events retained for audit.

## Compliance Controls (Engineering)
- Dataset classification, ownership, and retention tags.
- DSR runbook scaffolding for access/correction/deletion flows.
- Change trail for production releases and approvals.

## Open Compliance Decisions
- Approved Azure regions and residency boundaries.
- Compliance ownership model for DSR and policy exceptions.
