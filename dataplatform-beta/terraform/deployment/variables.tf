variable "tenant_id" {
  type        = string
  description = "Entra tenant ID."
}

variable "alert_email" {
  type        = string
  description = "Primary alert notification email for this environment."
}

variable "powerbi_group_owner_object_ids" {
  type        = list(string)
  description = "Object IDs that should own Power BI Entra groups."
  default     = []
}
