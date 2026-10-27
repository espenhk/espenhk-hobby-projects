# network module

Creates a virtual network, named subnets, optional NSGs, private DNS zones with VNet links, and private endpoints.

Current resources:
- azurerm_virtual_network
- azurerm_network_security_group (subnets with `create_nsg = true`)
- azurerm_subnet
- azurerm_subnet_network_security_group_association
- azurerm_private_dns_zone and azurerm_private_dns_zone_virtual_network_link (one per distinct `private_dns_zone_name`)
- azurerm_private_endpoint

Required inputs:
- resource_group_name
- location
- vnet_name
- address_space
- subnets (map: address_prefixes, optional service_delegation, optional create_nsg)

Optional inputs:
- private_endpoints (map: name, subnet_name, target_resource_id, subresource_names, private_dns_zone_name; default `{}`)
- tags
