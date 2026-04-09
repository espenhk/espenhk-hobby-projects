variable "resource_group_name" {
  type        = string
  description = "Resource group for connectivity resources."
}

variable "location" {
  type        = string
  description = "Azure location."
}

variable "vnet_name" {
  type        = string
  description = "Virtual network name."
}

variable "address_space" {
  type        = list(string)
  description = "VNet address space."
}

variable "subnets" {
  type = map(object({
    address_prefixes = list(string)
  }))
  description = "Subnet definitions."
}

variable "tags" {
  type        = map(string)
  description = "Environment tags."
  default     = {}
}
