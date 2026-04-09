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

variable "tags" {
  description = "Tags for monitor resources."
  type        = map(string)
  default     = {}
}
