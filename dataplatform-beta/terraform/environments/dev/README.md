# Environment Stacks

Each environment is split into independent Terraform stacks:
- foundation
- connectivity
- security
- data_platform
- governance
- observability
- powerbi_rbac

Run each stack independently with a dedicated backend key:
terraform init -backend-config=backend.hcl
terraform plan
