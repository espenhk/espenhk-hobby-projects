variable "catalog_name" {
  description = "Unity Catalog catalog name used for curated platform data products."
  type        = string
}

variable "schema_name" {
  description = "Unity Catalog schema name used for published assets."
  type        = string
}

variable "foundry_exchange_external_name" {
  description = "Name of the Unity Catalog external location for Foundry exchange."
  type        = string
}

variable "foundry_exchange_external_url" {
  description = "abfss URL backing the Foundry exchange external location."
  type        = string
}

variable "databricks_access_connector_id" {
  description = "Azure Databricks access connector resource ID used by the storage credential."
  type        = string
}

variable "databricks_access_connector_name" {
  description = "Azure Databricks access connector resource name (metadata/documentation)."
  type        = string
}
