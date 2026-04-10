terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 2.47.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.50.0"
    }
  }

  backend "azurerm" {}
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

provider "databricks" {
  host                        = startswith(module.databricks.workspace_url, "https://") ? module.databricks.workspace_url : "https://${module.databricks.workspace_url}"
  azure_workspace_resource_id = module.databricks.workspace_id
}
