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
  # host and azure_workspace_resource_id must be supplied as input variables
  # (var.databricks_workspace_url / var.databricks_workspace_resource_id) rather
  # than read from module outputs.  Provider configuration is evaluated during
  # planning, before any resources are created, so referencing computed module
  # outputs here causes "value not known until apply" plan errors.
  #
  # Workflow:
  #   1. First apply with databricks_workspace_url="" to provision the workspace.
  #   2. Copy the workspace URL and resource ID from outputs into tfvars.
  #   3. Subsequent applies use those static values in the provider block.
  host                        = var.databricks_workspace_url != "" ? (startswith(var.databricks_workspace_url, "https://") ? var.databricks_workspace_url : "https://${var.databricks_workspace_url}") : "https://placeholder.azuredatabricks.net"
  azure_workspace_resource_id = var.databricks_workspace_resource_id != "" ? var.databricks_workspace_resource_id : null
}
