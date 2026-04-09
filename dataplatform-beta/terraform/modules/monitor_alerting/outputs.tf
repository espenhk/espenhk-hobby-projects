output "action_group_id" {
  description = "ID of the created monitor action group."
  value       = azurerm_monitor_action_group.core.id
}
