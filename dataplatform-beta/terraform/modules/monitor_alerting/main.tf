terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
  }
}

resource "azurerm_monitor_action_group" "core" {
  name                = var.action_group_name
  resource_group_name = var.resource_group_name
  short_name          = var.short_name
  enabled             = true

  dynamic "email_receiver" {
    for_each = var.email_receivers
    content {
      name          = email_receiver.value.name
      email_address = email_receiver.value.email
    }
  }

  tags = var.tags
}

resource "azurerm_monitor_metric_alert" "platform" {
  for_each = {
    for alert in var.metric_alerts : alert.name => alert
  }

  name                = each.value.name
  resource_group_name = var.resource_group_name
  scopes              = [each.value.scope_resource_id]
  description         = each.value.description
  severity            = each.value.severity
  frequency           = each.value.frequency
  window_size         = each.value.window_size
  auto_mitigate       = true

  criteria {
    metric_namespace = each.value.metric_namespace
    metric_name      = each.value.metric_name
    aggregation      = each.value.aggregation
    operator         = each.value.operator
    threshold        = each.value.threshold
  }

  action {
    action_group_id = azurerm_monitor_action_group.core.id
  }

  tags = var.tags
}
