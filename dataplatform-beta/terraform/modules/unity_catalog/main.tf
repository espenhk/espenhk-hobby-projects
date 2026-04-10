terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.50.0"
    }
  }
}

resource "databricks_storage_credential" "foundry_exchange" {
  name = "sc_${var.foundry_exchange_external_name}"

  azure_managed_identity {
    access_connector_id = var.databricks_access_connector_id
  }

  comment = "Managed identity credential for approved Foundry exchange publishes"
}

resource "databricks_external_location" "foundry_exchange" {
  name            = var.foundry_exchange_external_name
  url             = trimsuffix(var.foundry_exchange_external_url, "/")
  credential_name = databricks_storage_credential.foundry_exchange.name
  comment         = "Approved Gold outputs that are shared to Foundry"
}
