terraform {
  required_version = ">= 1.6.0"
}

module "key_vault" {
  source = "../../../modules/key_vault"

  key_vault_name                = "kv-dpb-test-core"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  public_network_access_enabled = false
  tags                          = var.tags
}
