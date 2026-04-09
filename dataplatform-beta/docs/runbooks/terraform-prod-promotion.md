# Runbook: Terraform Production Promotion

## Trigger
- Approved infrastructure change to production stack.

## Preconditions
- Change ticket approved (CHG- or RFC- format and approval in change system).
- Relevant terraform-plan-prod workflow run completed without blocking changes.
- Required approvers available for terraform-prod-apply environment.

## Procedure
1. Run `ci/terraform-plan-prod.yml` for target stack with change ticket.
2. Review plan output for unexpected creates/destroys.
3. If accepted, run `ci/terraform-apply-prod.yml` with same ticket and stack.
4. Capture GitHub run ID, commit SHA, approver, and timestamps.

## Post-Apply Validation
1. Re-run terraform validate against target stack.
2. Confirm dependent smoke checks (Power BI or platform) still pass.
3. Record outcome in deployment evidence log.

## Rollback Guidance
- If change is reversible via Terraform, apply previous known-good commit.
- If not reversible cleanly, execute stack-specific rollback playbook and open incident.
