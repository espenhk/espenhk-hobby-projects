variable "vnet_name" {
  type        = string
  description = "Virtual network name."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for networking resources."
}

variable "location" {
  type        = string
  description = "Azure location."
}

variable "address_space" {
  type        = list(string)
  description = "Address space for virtual network."
}

variable "subnets" {
  description = "Subnet definitions by subnet name."
  type = map(object({
    address_prefixes   = list(string)
    service_delegation = optional(string, null)
    create_nsg         = optional(bool, false)
  }))
}

variable "private_endpoints" {
  description = "Private endpoints to create in the VNet and link to private DNS zones."
  type = map(object({
    name                  = string
    subnet_name           = string
    target_resource_id    = string
    subresource_names     = list(string)
    private_dns_zone_name = string
  }))
  default = {}
}

variable "tags" {
  type        = map(string)
  description = "Tags for network resources."
  default     = {}
}
