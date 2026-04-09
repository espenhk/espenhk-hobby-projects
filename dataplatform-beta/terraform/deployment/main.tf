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

  subnets = {
    dev = {
      snet-databricks-public  = { address_prefixes = ["10.40.1.0/24"] }
      snet-databricks-private = { address_prefixes = ["10.40.2.0/24"] }
    }
    test = {
      snet-databricks-public  = { address_prefixes = ["10.41.1.0/24"] }
      snet-databricks-private = { address_prefixes = ["10.41.2.0/24"] }
    }
    prod = {
      snet-databricks-public  = { address_prefixes = ["10.42.1.0/24"] }
      snet-databricks-private = { address_prefixes = ["10.42.2.0/24"] }
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
