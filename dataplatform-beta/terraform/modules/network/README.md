# network module

Creates a virtual network and named subnets for environment connectivity stacks.

Current resources:
- azurerm_virtual_network
- azurerm_subnet

Required inputs:
- resource_group_name
- location
- vnet_name
- address_space
- subnets

Optional inputs:
- tags
