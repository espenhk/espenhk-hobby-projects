terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
  }
}

resource "azurerm_consumption_budget_resource_group" "this" {
  for_each = var.resource_group_budgets

  name              = "budget-${each.key}"
  resource_group_id = each.value.resource_group_id
  amount            = each.value.amount_gbp
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_groups = [var.action_group_id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    contact_groups = [var.action_group_id]
  }
}
