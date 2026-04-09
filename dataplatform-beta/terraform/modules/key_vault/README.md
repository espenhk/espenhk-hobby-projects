# key_vault module

Creates an Azure Key Vault with security-focused defaults.

Current resources:
- azurerm_key_vault

Required inputs:
- key_vault_name
- resource_group_name
- location
- tenant_id

Optional inputs:
- sku_name
- soft_delete_retention_days
- purge_protection_enabled
- public_network_access_enabled
- tags
