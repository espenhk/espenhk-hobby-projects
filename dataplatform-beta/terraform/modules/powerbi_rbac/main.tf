terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 2.47.0"
    }
  }
}

locals {
  base = "${var.group_prefix}-${var.domain}"
}

resource "azuread_group" "admins" {
  display_name     = var.admins_display_name
  security_enabled = true
  owners           = var.owners_object_ids

  description = "Power BI administrators for ${local.base}."
}

resource "azuread_group" "developers" {
  display_name     = var.developers_display_name
  security_enabled = true
  owners           = var.owners_object_ids

  description = "Power BI developers for ${local.base}."
}

resource "azuread_group" "testers" {
  display_name     = var.testers_display_name
  security_enabled = true
  owners           = var.owners_object_ids

  description = "Power BI testers for ${local.base}."
}

resource "azuread_group" "consumers" {
  display_name     = var.consumers_display_name
  security_enabled = true
  owners           = var.owners_object_ids

  description = "Power BI consumers for ${local.base}."
}
