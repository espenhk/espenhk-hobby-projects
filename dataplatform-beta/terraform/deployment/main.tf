locals {
  env      = terraform.workspace
  location = "westeurope"
  platform = "dataplatform-beta"

  tags = {
    environment = local.env
    platform    = local.platform
  }

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
}

# ── Connectivity ───────────────────────────────────────────────────────────────
module "network" {
  source = "../modules/network"

  resource_group_name = "rg-dpb-${local.env}-network"
  location            = local.location
  vnet_name           = "vnet-dpb-${local.env}-core"
  address_space       = lookup(local.vnet_cidr, local.env, local.vnet_cidr["dev"])
  subnets             = lookup(local.subnets, local.env, local.subnets["dev"])
  tags                = local.tags
}

# ── Security ───────────────────────────────────────────────────────────────────
module "key_vault" {
  source = "../modules/key_vault"

  key_vault_name                = "kv-dpb-${local.env}-core"
  resource_group_name           = "rg-dpb-${local.env}-security"
  location                      = local.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  public_network_access_enabled = false
  tags                          = local.tags
}

# ── Observability ──────────────────────────────────────────────────────────────
module "monitor_alerting" {
  source = "../modules/monitor_alerting"

  resource_group_name = "rg-dpb-${local.env}-observability"
  action_group_name   = "ag-dpb-${local.env}-core"
  short_name          = "dpb${local.env}core"
  email_receivers = [
    {
      name  = "${local.env}-alerts"
      email = var.alert_email
    }
  ]
  tags = local.tags
}

# ── Data Platform — Databricks Workspace ───────────────────────────────────────
module "databricks_workspace" {
  source = "../modules/databricks_workspace"

  workspace_name      = "dbw-dpb-${local.env}-core"
  resource_group_name = "rg-dpb-${local.env}-data"
  location            = local.location
  sku                 = local.env == "prod" ? "premium" : "standard"

  virtual_network_id  = module.network.vnet_id
  public_subnet_name  = "snet-databricks-public"
  private_subnet_name = "snet-databricks-private"

  public_subnet_nsg_association_id  = module.network.subnet_nsg_association_ids["snet-databricks-public"]
  private_subnet_nsg_association_id = module.network.subnet_nsg_association_ids["snet-databricks-private"]

  tags = local.tags
}

# ── Cost Governance — Budgets ──────────────────────────────────────────────────
module "budgets" {
  source = "../modules/budgets_tags_policy"

  action_group_id   = module.monitor_alerting.action_group_id
  budget_start_date = var.budget_start_date

  resource_group_budgets = {
    network = {
      resource_group_id = "subscriptions/${var.subscription_id}/resourceGroups/rg-dpb-${local.env}-network"
      amount_gbp        = var.budget_amounts.network
    }
    security = {
      resource_group_id = "subscriptions/${var.subscription_id}/resourceGroups/rg-dpb-${local.env}-security"
      amount_gbp        = var.budget_amounts.security
    }
    data = {
      resource_group_id = "subscriptions/${var.subscription_id}/resourceGroups/rg-dpb-${local.env}-data"
      amount_gbp        = var.budget_amounts.data
    }
    observability = {
      resource_group_id = "subscriptions/${var.subscription_id}/resourceGroups/rg-dpb-${local.env}-observability"
      amount_gbp        = var.budget_amounts.observability
    }
  }
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
}
