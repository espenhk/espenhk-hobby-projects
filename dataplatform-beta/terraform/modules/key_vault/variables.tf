variable "key_vault_name" {
  description = "Name of the Key Vault."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Key Vault."
  type        = string
}

variable "location" {
  description = "Azure region for Key Vault."
  type        = string
}

variable "tenant_id" {
  description = "Entra tenant ID."
  type        = string
}

variable "sku_name" {
  description = "Key Vault SKU."
  type        = string
  default     = "standard"
}

variable "soft_delete_retention_days" {
  description = "Soft delete retention in days."
  type        = number
  default     = 90
}

variable "purge_protection_enabled" {
  description = "Enable purge protection."
  type        = bool
  default     = true
}

variable "public_network_access_enabled" {
  description = "Whether public network access is enabled."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags for Key Vault resource."
  type        = map(string)
  default     = {}
}
