terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
  }
}

resource "azurerm_virtual_network" "core" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space
  tags                = var.tags
}

resource "azurerm_network_security_group" "subnet_nsg" {
  for_each = { for k, v in var.subnets : k => v if v.create_nsg }

  name                = "nsg-${each.key}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_subnet" "subnets" {
  for_each             = var.subnets
  name                 = each.key
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.core.name
  address_prefixes     = each.value.address_prefixes

  dynamic "delegation" {
    for_each = each.value.service_delegation != null ? [each.value.service_delegation] : []
    content {
      name = "delegation"
      service_delegation {
        name = delegation.value
        actions = [
          "Microsoft.Network/virtualNetworks/subnets/join/action",
          "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
          "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
        ]
      }
    }
  }
}

resource "azurerm_subnet_network_security_group_association" "nsg_assoc" {
  for_each = { for k, v in var.subnets : k => v if v.create_nsg }

  subnet_id                 = azurerm_subnet.subnets[each.key].id
  network_security_group_id = azurerm_network_security_group.subnet_nsg[each.key].id
}

resource "azurerm_private_dns_zone" "zones" {
  for_each = {
    for zone_name in toset([for endpoint in values(var.private_endpoints) : endpoint.private_dns_zone_name]) : zone_name => zone_name
  }

  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "zone_links" {
  for_each = azurerm_private_dns_zone.zones

  name                  = "lnk-${replace(each.key, ".", "-")}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = each.value.name
  virtual_network_id    = azurerm_virtual_network.core.id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_private_endpoint" "endpoints" {
  for_each = var.private_endpoints

  name                = each.value.name
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = azurerm_subnet.subnets[each.value.subnet_name].id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-${each.key}"
    private_connection_resource_id = each.value.target_resource_id
    is_manual_connection           = false
    subresource_names              = each.value.subresource_names
  }

  private_dns_zone_group {
    name                 = "pdzg-${each.key}"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones[each.value.private_dns_zone_name].id]
  }
}
