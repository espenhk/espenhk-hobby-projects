# monitor_alerting module

Creates a baseline Azure Monitor action group for alert routing.

Current resources:
- azurerm_monitor_action_group

Required inputs:
- resource_group_name
- action_group_name
- short_name

Optional inputs:
- email_receivers
- tags
