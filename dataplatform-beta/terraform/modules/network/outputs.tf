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

output "private_endpoint_ids" {
  description = "Private endpoint resource IDs by logical name."
  value       = { for k, endpoint in azurerm_private_endpoint.endpoints : k => endpoint.id }
}

output "private_dns_zone_ids" {
  description = "Private DNS zone IDs by zone name."
  value       = { for k, zone in azurerm_private_dns_zone.zones : k => zone.id }
}
