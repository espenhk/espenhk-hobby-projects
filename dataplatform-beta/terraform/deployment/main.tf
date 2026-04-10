locals {
  env                  = terraform.workspace
  location             = "westeurope"
  platform             = "dataplatform-beta"
  storage_account_name = substr("sadpb${local.env}core${var.storage_account_suffix}", 0, 24)
  filesystem_names     = ["bronze", "silver", "gold", "checkpoints", "volumes", "foundry-exchange"]

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
      snet-private-endpoints = {
        address_prefixes   = ["10.40.10.0/24"]
        service_delegation = null
        create_nsg         = false
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
      snet-private-endpoints = {
        address_prefixes   = ["10.41.10.0/24"]
        service_delegation = null
        create_nsg         = false
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
      snet-private-endpoints = {
        address_prefixes   = ["10.42.10.0/24"]
        service_delegation = null
        create_nsg         = false
      }
    }
  }
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
  private_endpoints = {
    storage_blob = {
      name                  = "pep-dpb-${local.env}-storage-blob"
      subnet_name           = "snet-private-endpoints"
      target_resource_id    = module.storage.storage_account_id
      subresource_names     = ["blob"]
      private_dns_zone_name = "privatelink.blob.core.windows.net"
    }
    storage_dfs = {
      name                  = "pep-dpb-${local.env}-storage-dfs"
      subnet_name           = "snet-private-endpoints"
      target_resource_id    = module.storage.storage_account_id
      subresource_names     = ["dfs"]
      private_dns_zone_name = "privatelink.dfs.core.windows.net"
    }
    key_vault = {
      name                  = "pep-dpb-${local.env}-keyvault"
      subnet_name           = "snet-private-endpoints"
      target_resource_id    = module.key_vault.key_vault_id
      subresource_names     = ["vault"]
      private_dns_zone_name = "privatelink.vaultcore.azure.net"
    }
  }
  tags = local.tags
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

  resource_group_name          = azurerm_resource_group.main.name
  location                     = local.location
  environment                  = local.env
  action_group_name            = "ag-dpb-${local.env}-core"
  short_name                   = "dpb${local.env}core"
  log_analytics_workspace_name = "log-dpb-${local.env}-core"
  storage_account_id           = module.storage.storage_account_id
  key_vault_id                 = module.key_vault.key_vault_id
  email_receivers = [
    {
      name  = "${local.env}-alerts"
      email = var.alert_email
    }
  ]
  tags = local.tags
}

# ── Data Platform — Databricks Workspace ───────────────────────────────────────
module "databricks" {
  source = "../modules/databricks"

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

module "foundry" {
  source = "../modules/foundry"

  name                          = "fdry-dpb-${local.env}-core"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = local.location
  key_vault_id                  = module.key_vault.key_vault_id
  storage_account_id            = module.storage.storage_account_id
  public_network_access_enabled = true
  tags                          = local.tags
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

resource "azurerm_role_assignment" "foundry_storage_blob_reader" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = module.foundry.principal_id
}

resource "azurerm_key_vault_access_policy" "foundry_secret_reader" {
  key_vault_id = module.key_vault.key_vault_id
  tenant_id    = var.tenant_id
  object_id    = module.foundry.principal_id

  secret_permissions = [
    "Get",
    "List",
  ]
}

resource "azurerm_key_vault_secret" "foundry_databricks_pat" {
  count = var.databricks_connection_pat == "" ? 0 : 1

  name         = "foundry-databricks-pat"
  value        = var.databricks_connection_pat
  key_vault_id = module.key_vault.key_vault_id
  content_type = "Databricks PAT used by Foundry connection"

  depends_on = [azurerm_key_vault_access_policy.foundry_secret_reader]
}

resource "azurerm_key_vault_secret" "foundry_databricks_connection_contract" {
  name = "foundry-databricks-connection-contract"
  value = jsonencode({
    host                   = startswith(module.databricks.workspace_url, "https://") ? module.databricks.workspace_url : "https://${module.databricks.workspace_url}"
    workspace_resource_id  = module.databricks.workspace_id
    unity_catalog_catalog  = var.unity_catalog_catalog_name
    unity_catalog_schema   = var.unity_catalog_schema_name
    external_location_name = "foundry_exchange"
    external_location_url  = module.storage.filesystem_uris["foundry-exchange"]
    pat_secret_name        = "foundry-databricks-pat"
  })
  key_vault_id = module.key_vault.key_vault_id
  content_type = "Foundry to Databricks connection metadata"

  depends_on = [azurerm_key_vault_access_policy.foundry_secret_reader]
}

module "unity_catalog" {
  source = "../modules/unity_catalog"

  catalog_name                     = var.unity_catalog_catalog_name
  schema_name                      = var.unity_catalog_schema_name
  foundry_exchange_external_name   = "foundry_exchange"
  foundry_exchange_external_url    = module.storage.filesystem_uris["foundry-exchange"]
  databricks_access_connector_id   = azurerm_databricks_access_connector.volumes.id
  databricks_access_connector_name = azurerm_databricks_access_connector.volumes.name
}

# ── Cost Governance — Budgets ──────────────────────────────────────────────────
module "budgets" {
  source = "../modules/budget"

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
module "powerbi" {
  source = "../modules/powerbi"

  group_prefix            = "grp-pbi"
  domain                  = "core"
  admins_display_name     = "grp-pbi-core-admins-${local.env}"
  developers_display_name = "grp-pbi-core-developers-${local.env}"
  testers_display_name    = "grp-pbi-core-testers-${local.env}"
  consumers_display_name  = "grp-pbi-core-consumers-${local.env}"
  owners_object_ids       = var.powerbi_group_owner_object_ids

  tags = local.tags
}
