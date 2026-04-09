variable "powerbi_group_owner_object_ids" {
  type        = list(string)
  description = "Object IDs that should own Power BI Entra groups."
  default     = []
}
