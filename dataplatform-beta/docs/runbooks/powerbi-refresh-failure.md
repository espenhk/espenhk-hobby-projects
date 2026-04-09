# Runbook: Power BI Refresh Failure

## Trigger
- Dataset refresh fails for a Tier-1 semantic model.

## Severity Guidance
- P1: consecutive failures breach freshness SLO for Tier-1 model.
- P2: single failure with expected recovery in next cycle.

## Triage Steps
1. Confirm failure in Power BI refresh history.
2. Check Databricks Gold table freshness and upstream pipeline status.
3. Check deployment pipeline activity for recent model/report changes.
4. Validate service principal access and token acquisition path.

## Mitigation Steps
1. Retry refresh manually in Dev/Test if validating deployment impact.
2. Roll back to last known-good release if semantic model change is causal.
3. Trigger backfill pipeline if Gold table freshness is stale.

## Evidence to Capture
- Refresh failure timestamp and error code.
- Affected semantic model/report IDs.
- Mitigation action and completion timestamp.

## Exit Criteria
- Successful refresh observed.
- SLO impact assessed and communicated.
- Post-incident action item created for root cause.
