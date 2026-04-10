output "id" {
  description = "ARM resource ID of the Foundry backing workspace."
  value       = azurerm_machine_learning_workspace.this.id
}

output "workspace_id" {
  description = "Service workspace ID of the Foundry backing workspace."
  value       = azurerm_machine_learning_workspace.this.workspace_id
}

output "principal_id" {
  description = "System-assigned managed identity principal ID for the Foundry workspace."
  value       = azurerm_machine_learning_workspace.this.identity[0].principal_id
}

output "application_insights_id" {
  description = "Application Insights resource used by the Foundry workspace."
  value       = azurerm_application_insights.this.id
}