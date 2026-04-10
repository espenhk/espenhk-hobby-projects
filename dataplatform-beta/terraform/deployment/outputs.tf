output "vnet_id" {
  description = "Virtual network ID."
  value       = module.network.vnet_id
}

output "subnet_ids" {
  description = "Map of subnet IDs by subnet name."
  value       = module.network.subnet_ids
}

output "key_vault_id" {
  description = "Key Vault resource ID."
  value       = module.key_vault.key_vault_id
}

output "key_vault_uri" {
  description = "Key Vault URI."
  value       = module.key_vault.key_vault_uri
}

output "monitor_action_group_id" {
  description = "Monitor action group ID."
  value       = module.monitor_alerting.action_group_id
}

output "databricks_workspace_url" {
  description = "Databricks workspace URL."
  value       = module.databricks.workspace_url
}

output "databricks_workspace_id" {
  description = "Databricks workspace resource ID."
  value       = module.databricks.workspace_id
}

output "foundry_workspace_id" {
  description = "ARM resource ID of the Foundry backing workspace."
  value       = module.foundry.id
}

output "foundry_service_workspace_id" {
  description = "Service workspace ID of the Foundry backing workspace."
  value       = module.foundry.workspace_id
}

output "foundry_principal_id" {
  description = "Foundry managed identity principal ID."
  value       = module.foundry.principal_id
}

output "storage_account_name" {
  description = "ADLS storage account name for medallion data and Databricks volumes."
  value       = module.storage.storage_account_name
}

output "storage_filesystem_uris" {
  description = "abfss URIs for medallion, checkpoint, and volume filesystems."
  value       = module.storage.filesystem_uris
}

output "foundry_exchange_uri" {
  description = "ADLS exchange URI that Databricks can publish curated files to and Foundry can read from."
  value       = module.storage.filesystem_uris["foundry-exchange"]
}

output "databricks_access_connector_id" {
  description = "Databricks access connector used for storage-backed volumes."
  value       = azurerm_databricks_access_connector.volumes.id
}

output "powerbi_groups" {
  description = "Power BI Entra group details."
  value = {
    admins     = module.powerbi.admins_group
    developers = module.powerbi.developers_group
    testers    = module.powerbi.testers_group
    consumers  = module.powerbi.consumers_group
  }
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID used for platform observability."
  value       = module.monitor_alerting.log_analytics_workspace_id
}

output "log_analytics_workspace_name" {
  description = "Log Analytics workspace name for querying platform logs."
  value       = module.monitor_alerting.log_analytics_workspace_name
}

output "foundry_exchange_external_location_name" {
  description = "Unity Catalog external location name for approved Foundry exchange outputs."
  value       = module.unity_catalog.foundry_exchange_external_location_name
}
