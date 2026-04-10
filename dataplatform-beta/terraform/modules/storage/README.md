# storage module

Provisions an Azure Data Lake Storage Gen2 (ADLS Gen2) account and one or more named filesystems for medallion-layer data, checkpoints, and Databricks volumes.

## Resources created

| Resource | Description |
|---|---|
| `azurerm_storage_account` | StorageV2 account with hierarchical namespace, TLS 1.2 minimum, public network access disabled, shared-key auth disabled, and OAuth as default authentication. |
| `azurerm_storage_data_lake_gen2_filesystem` | One filesystem per entry in `var.filesystem_names` (e.g. `bronze`, `silver`, `gold`, `checkpoints`, `volumes`, `foundry-exchange`). |

## Security defaults

- Public network access is disabled — access is expected via private endpoints provisioned by the `network` module.
- Shared access key auth is disabled; all access must use Entra (OAuth) or managed identities.
- Blob versioning, change feed, and soft-delete retention (14 days) are enabled.

## Required inputs

| Variable | Type | Description |
|---|---|---|
| `storage_account_name` | `string` | Globally unique storage account name (max 24 chars, lowercase). |
| `resource_group_name` | `string` | Resource group in which to create the account. |
| `location` | `string` | Azure region. |
| `filesystem_names` | `list(string)` | Names of the ADLS Gen2 filesystems to create. |

## Optional inputs

| Variable | Default | Description |
|---|---|---|
| `account_tier` | `"Standard"` | Storage account performance tier. |
| `account_replication_type` | `"LRS"` | Replication type; use `"ZRS"` for production workloads. |
| `tags` | `{}` | Tags applied to the storage account. |

## Outputs

| Output | Description |
|---|---|
| `storage_account_id` | Resource ID of the storage account. |
| `storage_account_name` | Name of the storage account. |
| `dfs_endpoint` | Primary DFS endpoint for ADLS access from Databricks. |
| `filesystem_ids` | Map of filesystem name → resource ID. |
| `filesystem_uris` | Map of filesystem name → `abfss://` URI. |

## RBAC

Assign `Storage Blob Data Contributor` to the Databricks access connector managed identity and `Storage Blob Data Reader` to the Foundry workspace identity in the deployment root (`main.tf`).
