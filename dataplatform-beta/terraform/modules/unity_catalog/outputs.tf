output "foundry_exchange_external_location_name" {
  description = "Unity Catalog external location name for the Foundry exchange zone."
  value       = databricks_external_location.foundry_exchange.name
}

output "foundry_exchange_external_location_url" {
  description = "Unity Catalog external location URL for the Foundry exchange zone."
  value       = databricks_external_location.foundry_exchange.url
}

output "storage_credential_name" {
  description = "Storage credential name used by the Foundry exchange external location."
  value       = databricks_storage_credential.foundry_exchange.name
}
