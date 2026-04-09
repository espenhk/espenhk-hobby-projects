locals {
  env                  = terraform.workspace
  location             = "westeurope"
  platform             = "dataplatform-beta"
  storage_account_name = substr("sadpb${local.env}core${var.storage_account_suffix}", 0, 24)
  filesystem_names     = ["bronze", "silver", "gold", "checkpoints", "volumes"]

  tags = {
    environment = local.env
    platform    = local.platform
  }

  resource_group_name = "rg-dpb-${local.env}-network"

  # Per-workspace address spaces (10.40=dev, 10.41=test, 10.42=prod)
  vnet_cidr = {
    dev  = ["10.40.0.0/16"]
    test = ["10.41.0.0/16"]
    prod = ["10.42.0.0/16"]
  }

  # Subnets include Databricks delegation and NSG requirements
  subnets = {
    dev = {
      snet-databricks-public = {
        address_prefixes   = ["10.40.1.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
      snet-databricks-private = {
        address_prefixes   = ["10.40.2.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
    }
    test = {
      snet-databricks-public = {
        address_prefixes   = ["10.41.1.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
      snet-databricks-private = {
        address_prefixes   = ["10.41.2.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
    }
    prod = {
      snet-databricks-public = {
        address_prefixes   = ["10.42.1.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
      snet-databricks-private = {
        address_prefixes   = ["10.42.2.0/24"]
        service_delegation = "Microsoft.Databricks/workspaces"
        create_nsg         = true
      }
    }
  }

  metric_alerts = [
    {
      name              = "ma-${local.env}-storage-availability-low"
      description       = "Storage availability dropped below 99 percent. This usually indicates the platform data plane is degraded or unreachable."
      severity          = 1
      scope_resource_id = module.storage.storage_account_id
      metric_namespace  = "Microsoft.Storage/storageAccounts"
      metric_name       = "Availability"
      aggregation       = "Average"
      operator          = "LessThan"
      threshold         = 99
      frequency         = "PT5M"
      window_size       = "PT15M"
    },
    {
      name              = "ma-${local.env}-storage-latency-high"
      description       = "Blob end-to-end latency is elevated. Databricks reads, writes, checkpoints, or volume access may be stuck or timing out."
      severity          = 2
      scope_resource_id = module.storage.storage_account_id
      metric_namespace  = "Microsoft.Storage/storageAccounts"
      metric_name       = "SuccessE2ELatency"
      aggregation       = "Average"
      operator          = "GreaterThan"
      threshold         = 2000
      frequency         = "PT5M"
      window_size       = "PT15M"
    },
    {
      name              = "ma-${local.env}-keyvault-availability-low"
      description       = "Key Vault availability dropped below 99 percent. Secret resolution and downstream workloads are likely impaired."
      severity          = 1
      scope_resource_id = module.key_vault.key_vault_id
      metric_namespace  = "Microsoft.KeyVault/vaults"
      metric_name       = "Availability"
      aggregation       = "Average"
      operator          = "LessThan"
      threshold         = 99
      frequency         = "PT5M"
      window_size       = "PT15M"
    }
  ]
}

resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = local.location
  tags     = local.tags
}

# ── Connectivity ───────────────────────────────────────────────────────────────
module "network" {
  source = "../modules/network"

  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  vnet_name           = "vnet-dpb-${local.env}-core"
  address_space       = lookup(local.vnet_cidr, local.env, local.vnet_cidr["dev"])
  subnets             = lookup(local.subnets, local.env, local.subnets["dev"])
  tags                = local.tags
}

module "storage" {
  source = "../modules/storage"

  storage_account_name     = local.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = local.location
  filesystem_names         = local.filesystem_names
  account_tier             = "Standard"
  account_replication_type = local.env == "prod" ? "ZRS" : "LRS"
  tags                     = local.tags
}

# ── Security ───────────────────────────────────────────────────────────────────
module "key_vault" {
  source = "../modules/key_vault"

  key_vault_name                = "kv-dpb-${local.env}-core"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = local.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  public_network_access_enabled = false
  tags                          = local.tags
}

# ── Observability ──────────────────────────────────────────────────────────────
module "monitor_alerting" {
  source = "../modules/monitor_alerting"

  resource_group_name = azurerm_resource_group.main.name
  action_group_name   = "ag-dpb-${local.env}-core"
  short_name          = "dpb${local.env}core"
  email_receivers = [
    {
      name  = "${local.env}-alerts"
      email = var.alert_email
    }
  ]
  metric_alerts = local.metric_alerts
  tags          = local.tags
}

# ── Data Platform — Databricks Workspace ───────────────────────────────────────
module "databricks_workspace" {
  source = "../modules/databricks_workspace"

  workspace_name      = "dbw-dpb-${local.env}-core"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  sku                 = local.env == "prod" ? "premium" : "standard"

  virtual_network_id  = module.network.vnet_id
  public_subnet_name  = "snet-databricks-public"
  private_subnet_name = "snet-databricks-private"

  public_subnet_nsg_association_id  = module.network.subnet_nsg_association_ids["snet-databricks-public"]
  private_subnet_nsg_association_id = module.network.subnet_nsg_association_ids["snet-databricks-private"]

  tags = local.tags
}

resource "azurerm_databricks_access_connector" "volumes" {
  name                = "dbc-dpb-${local.env}-volumes"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

resource "azurerm_role_assignment" "databricks_storage_blob_contributor" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.volumes.identity[0].principal_id
}

# ── Cost Governance — Budgets ──────────────────────────────────────────────────
module "budgets" {
  source = "../modules/budgets_tags_policy"

  action_group_id     = module.monitor_alerting.action_group_id
  budget_start_date   = var.budget_start_date
  resource_group_name = azurerm_resource_group.main.name
  resource_group_budgets = {
    network = {
      resource_group_id = azurerm_resource_group.main.id
      amount_gbp        = var.budget_amounts.network
    }
    security = {
      resource_group_id = azurerm_resource_group.main.id
      amount_gbp        = var.budget_amounts.security
    }
    data = {
      resource_group_id = azurerm_resource_group.main.id
      amount_gbp        = var.budget_amounts.data
    }
    observability = {
      resource_group_id = azurerm_resource_group.main.id
      amount_gbp        = var.budget_amounts.observability
    }
  }

  tags = local.tags
}

# ── Power BI RBAC ──────────────────────────────────────────────────────────────
module "powerbi_rbac" {
  source = "../modules/powerbi_rbac"

  group_prefix            = "grp-pbi"
  domain                  = "core"
  admins_display_name     = "grp-pbi-core-admins-${local.env}"
  developers_display_name = "grp-pbi-core-developers-${local.env}"
  testers_display_name    = "grp-pbi-core-testers-${local.env}"
  consumers_display_name  = "grp-pbi-core-consumers-${local.env}"
  owners_object_ids       = var.powerbi_group_owner_object_ids

  tags = local.tags
}
