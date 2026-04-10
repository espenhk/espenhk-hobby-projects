variable "group_prefix" {
  type        = string
  description = "Prefix for Entra groups used by Power BI RBAC."
}

variable "domain" {
  type        = string
  description = "Business domain, used in group naming."
}

variable "admins_display_name" {
  type        = string
  description = "Display name for Power BI admins group."
}

variable "developers_display_name" {
  type        = string
  description = "Display name for Power BI developers group."
}

variable "testers_display_name" {
  type        = string
  description = "Display name for Power BI testers group."
}

variable "consumers_display_name" {
  type        = string
  description = "Display name for Power BI consumers group."
}

variable "owners_object_ids" {
  type        = list(string)
  description = "Object IDs that should own the Entra groups."
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to created resources."
  default     = {}
}
