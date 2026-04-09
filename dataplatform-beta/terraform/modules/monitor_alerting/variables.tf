variable "resource_group_name" {
  description = "Resource group where the action group is created."
  type        = string
}

variable "action_group_name" {
  description = "Action group name."
  type        = string
}

variable "short_name" {
  description = "Short name (<=12 chars) for monitor action group."
  type        = string
}

variable "email_receivers" {
  description = "List of email receivers for alert notifications."
  type = list(object({
    name  = string
    email = string
  }))
  default = []
}

variable "metric_alerts" {
  description = "Metric alerts to create for platform dependencies that indicate probable breakage."
  type = list(object({
    name              = string
    description       = string
    severity          = number
    scope_resource_id = string
    metric_namespace  = string
    metric_name       = string
    aggregation       = string
    operator          = string
    threshold         = number
    frequency         = string
    window_size       = string
  }))
  default = []
}

variable "tags" {
  description = "Tags for monitor resources."
  type        = map(string)
  default     = {}
}
