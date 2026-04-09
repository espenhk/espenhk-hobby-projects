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
  value       = module.databricks_workspace.workspace_url
}

output "databricks_workspace_id" {
  description = "Databricks workspace resource ID."
  value       = module.databricks_workspace.workspace_id
}

output "powerbi_groups" {
  description = "Power BI Entra group details."
  value = {
    admins     = module.powerbi_rbac.admins_group
    developers = module.powerbi_rbac.developers_group
    testers    = module.powerbi_rbac.testers_group
    consumers  = module.powerbi_rbac.consumers_group
  }
}
