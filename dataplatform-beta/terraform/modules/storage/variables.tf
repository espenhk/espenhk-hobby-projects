variable "storage_account_name" {
  description = "Globally unique storage account name."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the storage account."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "account_tier" {
  description = "Storage account tier."
  type        = string
  default     = "Standard"
}

variable "account_replication_type" {
  description = "Storage account replication type."
  type        = string
  default     = "LRS"
}

variable "filesystem_names" {
  description = "ADLS Gen2 filesystems to create for medallion data, checkpoints, and Databricks volumes."
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to storage resources."
  type        = map(string)
  default     = {}
}