variable "name" {
  description = "Azure AI Foundry backing workspace name."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Foundry workspace."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault used by the Foundry workspace and for Databricks connection secrets."
  type        = string
}

variable "storage_account_id" {
  description = "Storage account that holds the Foundry/Databricks exchange zone."
  type        = string
}

variable "public_network_access_enabled" {
  description = "Whether Foundry workspace public network access is enabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to Foundry resources."
  type        = map(string)
  default     = {}
}