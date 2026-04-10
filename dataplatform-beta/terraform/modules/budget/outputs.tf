output "budget_ids" {
  description = "Map of created budget resource IDs by label."
  value       = { for k, b in azurerm_consumption_budget_resource_group.this : k => b.id }
}
