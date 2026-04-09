module "powerbi_rbac_core" {
  source = "../../../modules/powerbi_rbac"

  group_prefix = "grp-pbi"
  domain       = "core"

  admins_display_name     = "grp-pbi-core-admins"
  developers_display_name = "grp-pbi-core-developers"
  testers_display_name    = "grp-pbi-core-testers"
  consumers_display_name  = "grp-pbi-core-consumers"

  owners_object_ids = var.powerbi_group_owner_object_ids
}
