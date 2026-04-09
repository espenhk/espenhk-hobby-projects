output "vnet_id" {
  description = "Virtual network ID."
  value       = azurerm_virtual_network.core.id
}

output "subnet_ids" {
  description = "Map of subnet IDs by subnet name."
  value       = { for k, subnet in azurerm_subnet.subnets : k => subnet.id }
}

output "subnet_nsg_association_ids" {
  description = "Map of NSG association IDs by subnet name (only for subnets with create_nsg=true)."
  value       = { for k, assoc in azurerm_subnet_network_security_group_association.nsg_assoc : k => assoc.id }
}
