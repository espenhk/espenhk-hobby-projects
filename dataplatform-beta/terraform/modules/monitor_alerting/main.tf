terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
  }
}

locals {
  baseline_metric_alerts = [
    {
      name              = "ma-${var.environment}-storage-availability-low"
      description       = "Storage availability dropped below 99 percent. This usually indicates the platform data plane is degraded or unreachable."
      severity          = 1
      scope_resource_id = var.storage_account_id
      metric_namespace  = "Microsoft.Storage/storageAccounts"
      metric_name       = "Availability"
      aggregation       = "Average"
      operator          = "LessThan"
      threshold         = 99
      frequency         = "PT5M"
      window_size       = "PT15M"
    },
    {
      name              = "ma-${var.environment}-storage-latency-high"
      description       = "Blob end-to-end latency is elevated. Databricks reads, writes, checkpoints, or volume access may be stuck or timing out."
      severity          = 2
      scope_resource_id = var.storage_account_id
      metric_namespace  = "Microsoft.Storage/storageAccounts"
      metric_name       = "SuccessE2ELatency"
      aggregation       = "Average"
      operator          = "GreaterThan"
      threshold         = 2000
      frequency         = "PT5M"
      window_size       = "PT15M"
    },
    {
      name              = "ma-${var.environment}-keyvault-availability-low"
      description       = "Key Vault availability dropped below 99 percent. Secret resolution and downstream workloads are likely impaired."
      severity          = 1
      scope_resource_id = var.key_vault_id
      metric_namespace  = "Microsoft.KeyVault/vaults"
      metric_name       = "Availability"
      aggregation       = "Average"
      operator          = "LessThan"
      threshold         = 99
      frequency         = "PT5M"
      window_size       = "PT15M"
    }
  ]

  effective_metric_alerts = concat(local.baseline_metric_alerts, var.metric_alerts)
}

resource "azurerm_log_analytics_workspace" "core" {
  name                = var.log_analytics_workspace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_in_days
  tags                = var.tags
}

resource "azurerm_log_analytics_saved_search" "recommended" {
  for_each = {
    for item in var.saved_searches : item.name => item
  }

  name                       = each.value.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.core.id
  category                   = each.value.category
  display_name               = each.value.name
  query                      = each.value.query
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
    for alert in local.effective_metric_alerts : alert.name => alert
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
