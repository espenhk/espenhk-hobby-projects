variable "tenant_id" {
  type        = string
  description = "Entra tenant ID."
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID (used to construct resource group IDs for budgets)."
}

variable "alert_email" {
  type        = string
  description = "Primary alert notification email for this environment."
}

variable "powerbi_group_owner_object_ids" {
  type        = list(string)
  description = "Object IDs that should own Power BI Entra groups."
  default     = []
}

variable "budget_start_date" {
  type        = string
  description = "Budget period start date in RFC3339 format, e.g. 2026-04-01T00:00:00Z."
  default     = "2026-04-01T00:00:00Z"
}

variable "budget_amounts" {
  description = "Monthly budget limits in GBP per resource group category."
  type = object({
    network       = number
    security      = number
    data          = number
    observability = number
  })
  default = {
    network       = 50
    security      = 20
    data          = 200
    observability = 20
  }
}

variable "storage_account_suffix" {
  type        = string
  description = "Short suffix added to the storage account name to keep it globally unique. Use lowercase letters and digits only."
  default     = "001"
}

variable "databricks_connection_pat" {
  type        = string
  description = "Databricks PAT stored in Key Vault for Foundry connectivity. Leave empty if injected out-of-band."
  default     = ""
  sensitive   = true
}

variable "unity_catalog_catalog_name" {
  type        = string
  description = "Unity Catalog catalog that hosts curated assets and external locations."
  default     = "core"
}

variable "unity_catalog_schema_name" {
  type        = string
  description = "Unity Catalog schema that contains published exchange references."
  default     = "published"
}
