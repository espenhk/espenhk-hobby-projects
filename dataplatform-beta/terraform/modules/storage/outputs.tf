output "storage_account_id" {
  description = "Storage account resource ID."
  value       = azurerm_storage_account.this.id
}

output "storage_account_name" {
  description = "Storage account name."
  value       = azurerm_storage_account.this.name
}

output "dfs_endpoint" {
  description = "DFS endpoint for ADLS access from Databricks."
  value       = azurerm_storage_account.this.primary_dfs_endpoint
}

output "filesystem_ids" {
  description = "Filesystem IDs by filesystem name."
  value       = { for name, filesystem in azurerm_storage_data_lake_gen2_filesystem.filesystems : name => filesystem.id }
}

output "filesystem_uris" {
  description = "abfss URIs by filesystem name."
  value = {
    for name, filesystem in azurerm_storage_data_lake_gen2_filesystem.filesystems :
    name => format("abfss://%s@%s.dfs.core.windows.net/", filesystem.name, azurerm_storage_account.this.name)
  }
}