# unity_catalog module

Manages Unity Catalog resources that expose the approved Gold / Foundry exchange zone to Databricks.

## Resources created

| Resource | Description |
|---|---|
| `databricks_storage_credential` | Managed identity storage credential backed by the Databricks access connector, used to authenticate read/write operations on the Foundry exchange ADLS path. |
| `databricks_external_location` | External location registered in Unity Catalog pointing to the `foundry-exchange` ADLS Gen2 filesystem. Gold outputs approved for publishing are written here. |

## Required inputs

| Variable | Type | Description |
|---|---|---|
| `catalog_name` | `string` | Unity Catalog catalog that hosts curated platform data products. |
| `schema_name` | `string` | Unity Catalog schema for published exchange assets. |
| `foundry_exchange_external_name` | `string` | Name used for the storage credential and external location. |
| `foundry_exchange_external_url` | `string` | `abfss://` URL backing the external location (e.g. the `foundry-exchange` filesystem URI from the `storage` module). |
| `databricks_access_connector_id` | `string` | Azure resource ID of the Databricks access connector whose managed identity is granted access to the ADLS path. |
| `databricks_access_connector_name` | `string` | Access connector resource name (used for documentation/tagging). |

## Outputs

| Output | Description |
|---|---|
| `foundry_exchange_external_location_name` | UC external location name. |
| `foundry_exchange_external_location_url` | UC external location URL. |
| `storage_credential_name` | Storage credential name used by the external location. |

## IAM requirements

The Databricks access connector principal must have `Storage Blob Data Contributor` on the ADLS storage account before this module is applied. That role assignment is performed in the deployment root (`main.tf`) via `azurerm_role_assignment.databricks_storage_blob_contributor`.

## Notes

- The Databricks provider used by this module must be configured with a workspace URL and credentials that have Unity Catalog metastore admin or account admin privileges.
- Apply this module only after the Databricks workspace is fully provisioned (see two-phase apply note in `providers.tf`).
