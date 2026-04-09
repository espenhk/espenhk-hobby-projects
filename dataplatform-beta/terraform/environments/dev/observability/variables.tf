variable "resource_group_name" {
  type        = string
  description = "Resource group for observability resources."
}

variable "alert_email" {
  type        = string
  description = "Primary alert notification email."
}

variable "tags" {
  type        = map(string)
  description = "Environment tags."
  default     = {}
}
