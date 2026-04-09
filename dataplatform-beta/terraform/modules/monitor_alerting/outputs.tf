output "action_group_id" {
  description = "ID of the created monitor action group."
  value       = azurerm_monitor_action_group.core.id
}

output "metric_alert_ids" {
  description = "Metric alert IDs by alert name."
  value       = { for name, alert in azurerm_monitor_metric_alert.platform : name => alert.id }
}
