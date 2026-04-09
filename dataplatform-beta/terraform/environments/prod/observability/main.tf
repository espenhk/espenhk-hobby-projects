terraform {
  required_version = ">= 1.6.0"
}

module "monitor_alerting" {
  source = "../../../modules/monitor_alerting"

  resource_group_name = var.resource_group_name
  action_group_name   = "ag-dpb-prod-core"
  short_name          = "dpbprodcore"
  email_receivers = [
    {
      name  = "prod-alerts"
      email = var.alert_email
    }
  ]
  tags = var.tags
}
