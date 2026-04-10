variable "workspace_name" {
  description = "Name of the Databricks workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Databricks workspace."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "sku" {
  description = "Databricks SKU: trial, standard, or premium."
  type        = string
  default     = "premium"
}

variable "virtual_network_id" {
  description = "Resource ID of the VNet for VNet injection."
  type        = string
}

variable "public_subnet_name" {
  description = "Name of the public (container) subnet for Databricks."
  type        = string
}

variable "private_subnet_name" {
  description = "Name of the private (host) subnet for Databricks."
  type        = string
}

variable "public_subnet_nsg_association_id" {
  description = "NSG association resource ID for the public subnet."
  type        = string
}

variable "private_subnet_nsg_association_id" {
  description = "NSG association resource ID for the private subnet."
  type        = string
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
