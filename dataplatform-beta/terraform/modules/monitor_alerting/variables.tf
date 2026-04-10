variable "resource_group_name" {
  description = "Resource group where the action group is created."
  type        = string
}

variable "location" {
  description = "Azure location for observability resources."
  type        = string
}

variable "environment" {
  description = "Environment code used in naming and queries (dev/test/prod)."
  type        = string
}

variable "action_group_name" {
  description = "Action group name."
  type        = string
}

variable "short_name" {
  description = "Short name (<=12 chars) for monitor action group."
  type        = string
}

variable "log_analytics_workspace_name" {
  description = "Log Analytics workspace name used for diagnostics and operational analytics."
  type        = string
}

variable "log_analytics_retention_in_days" {
  description = "Retention period in days for Log Analytics workspace data."
  type        = number
  default     = 30
}

variable "storage_account_id" {
  description = "Storage account resource ID monitored for platform health."
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID monitored for platform health."
  type        = string
}

variable "email_receivers" {
  description = "List of email receivers for alert notifications."
  type = list(object({
    name  = string
    email = string
  }))
  default = []
}

variable "metric_alerts" {
  description = "Additional metric alerts to create beyond built-in baseline alerts."
  type = list(object({
    name              = string
    description       = string
    severity          = number
    scope_resource_id = string
    metric_namespace  = string
    metric_name       = string
    aggregation       = string
    operator          = string
    threshold         = number
    frequency         = string
    window_size       = string
  }))
  default = []
}

variable "saved_searches" {
  description = "Log Analytics saved searches to bootstrap operations dashboards and investigations."
  type = list(object({
    name     = string
    category = string
    query    = string
  }))
  default = [
    {
      name     = "StorageAvailabilityTrend"
      category = "Platform Health"
      query    = "AzureMetrics | where ResourceProvider == \"MICROSOFT.STORAGE\" and MetricName == \"Availability\" | summarize avg(Val) by bin(TimeGenerated, 15m), Resource"
    },
    {
      name     = "KeyVaultFailedRequests"
      category = "Security & Access"
      query    = "AzureDiagnostics | where ResourceProvider == \"MICROSOFT.KEYVAULT\" and ResultType !in (\"Success\", \"Succeeded\") | summarize failures=count() by bin(TimeGenerated, 15m), Resource"
    },
    {
      name     = "DatabricksErrorSignals"
      category = "Data Platform"
      query    = "AzureDiagnostics | where ResourceProvider contains \"DATABRICKS\" and (Level =~ \"Error\" or Status_s =~ \"Failed\") | summarize errors=count() by bin(TimeGenerated, 15m), Resource"
    }
  ]
}

variable "tags" {
  description = "Tags for monitor resources."
  type        = map(string)
  default     = {}
}
