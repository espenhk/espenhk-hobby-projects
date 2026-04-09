output "vnet_id" {
  description = "Virtual network ID."
  value       = azurerm_virtual_network.core.id
}

output "subnet_ids" {
  description = "Map of subnet IDs by subnet name."
  value = {
    for k, subnet in azurerm_subnet.subnets : k => subnet.id
  }
}
