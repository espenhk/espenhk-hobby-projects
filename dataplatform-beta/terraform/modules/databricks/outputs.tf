output "workspace_id" {
  description = "Databricks workspace resource ID."
  value       = azurerm_databricks_workspace.this.id
}

output "workspace_url" {
  description = "Databricks workspace URL."
  value       = azurerm_databricks_workspace.this.workspace_url
}

output "workspace_resource_id" {
  description = "Databricks managed resource group ID."
  value       = azurerm_databricks_workspace.this.managed_resource_group_id
}
