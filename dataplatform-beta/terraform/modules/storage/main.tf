terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
  }
}

resource "azurerm_storage_account" "this" {
  name                            = var.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = var.account_tier
  account_replication_type        = var.account_replication_type
  account_kind                    = "StorageV2"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  blob_properties {
    versioning_enabled       = true
    change_feed_enabled      = true
    last_access_time_enabled = true

    delete_retention_policy {
      days = 14
    }

    container_delete_retention_policy {
      days = 14
    }
  }

  tags = var.tags
}

resource "azurerm_storage_data_lake_gen2_filesystem" "filesystems" {
  for_each = toset(var.filesystem_names)

  name               = each.value
  storage_account_id = azurerm_storage_account.this.id
}