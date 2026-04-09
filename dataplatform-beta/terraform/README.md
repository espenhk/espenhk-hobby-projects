# Terraform Scaffold for Power BI RBAC

This scaffold creates Entra groups used by the Power BI workspace and deployment pipeline access model.

## Module
- modules/powerbi_rbac

## Environment Example
- environments/dev/powerbi-rbac.tf

## Usage
1. Configure AzureAD provider credentials.
2. Update owners in environments/dev/terraform.tfvars.
3. Run terraform init/plan/apply in the environment folder.

## Outputs
- admins_group
- developers_group
- testers_group
- consumers_group

These outputs should be used to bind workspace roles and deployment pipeline permissions.
