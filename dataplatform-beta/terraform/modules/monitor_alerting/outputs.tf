output "action_group_id" {
  description = "ID of the created monitor action group."
  value       = azurerm_monitor_action_group.core.id
}

output "metric_alert_ids" {
  description = "Metric alert IDs by alert name."
  value       = { for name, alert in azurerm_monitor_metric_alert.platform : name => alert.id }
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.core.id
}

output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.core.name
}
