variable "resource_group_name" {
  type        = string
  description = "Resource group for security stack resources."
}

variable "location" {
  type        = string
  description = "Azure location."
}

variable "tenant_id" {
  type        = string
  description = "Entra tenant ID."
}

variable "tags" {
  type        = map(string)
  description = "Environment tags."
  default     = {}
}
