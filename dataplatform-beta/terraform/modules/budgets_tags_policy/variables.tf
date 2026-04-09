variable "resource_group_budgets" {
  description = "Map of resource group budgets. Key is a label; value provides RG ID and monthly spend limit."
  type = map(object({
    resource_group_id = string
    amount_gbp        = number
  }))
  default = {}
}

variable "budget_start_date" {
  description = "Budget period start date in RFC3339 format (first day of a month, e.g. 2026-04-01T00:00:00Z)."
  type        = string
}

variable "action_group_id" {
  description = "Monitor action group ID to notify on budget threshold breaches."
  type        = string
}
