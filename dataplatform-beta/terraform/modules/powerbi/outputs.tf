output "admins_group" {
  value = {
    id           = azuread_group.admins.id
    display_name = azuread_group.admins.display_name
    object_id    = azuread_group.admins.object_id
  }
}

output "developers_group" {
  value = {
    id           = azuread_group.developers.id
    display_name = azuread_group.developers.display_name
    object_id    = azuread_group.developers.object_id
  }
}

output "testers_group" {
  value = {
    id           = azuread_group.testers.id
    display_name = azuread_group.testers.display_name
    object_id    = azuread_group.testers.object_id
  }
}

output "consumers_group" {
  value = {
    id           = azuread_group.consumers.id
    display_name = azuread_group.consumers.display_name
    object_id    = azuread_group.consumers.object_id
  }
}
