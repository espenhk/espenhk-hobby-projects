output "key_vault_id" {
  description = "ID of the created Key Vault."
  value       = azurerm_key_vault.core.id
}

output "key_vault_uri" {
  description = "URI of the created Key Vault."
  value       = azurerm_key_vault.core.vault_uri
}
