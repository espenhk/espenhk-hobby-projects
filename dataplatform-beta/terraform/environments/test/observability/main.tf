terraform {
  required_version = ">= 1.6.0"
}

module "monitor_alerting" {
  source = "../../../modules/monitor_alerting"

  resource_group_name = var.resource_group_name
  action_group_name   = "ag-dpb-test-core"
  short_name          = "dpbtestcore"
  email_receivers = [
    {
      name  = "test-alerts"
      email = var.alert_email
    }
  ]
  tags = var.tags
}
