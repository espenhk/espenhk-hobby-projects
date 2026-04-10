# Terraform Scaffold

This scaffold defines a stack-based Terraform layout per environment and currently implements the Power BI RBAC stack.

## Module
- modules/powerbi

## Environment Stacks
- environments/dev/<stack>
- environments/test/<stack>
- environments/prod/<stack>

Current implemented stack:
- powerbi

## Usage
1. Configure AzureAD provider credentials.
2. Update owners in the target environment tfvars file.
3. Run terraform init/plan/apply in the target environment stack folder.

Example:
- dev: environments/dev/powerbi/terraform.tfvars.example
- test: environments/test/powerbi/terraform.tfvars.example
- prod: environments/prod/powerbi/terraform.tfvars.example

## Outputs
- admins_group
- developers_group
- testers_group
- consumers_group

These outputs should be used to bind workspace roles and deployment pipeline permissions.
