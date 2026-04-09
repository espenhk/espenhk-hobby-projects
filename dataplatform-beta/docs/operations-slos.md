# Operations and SLO Baseline

## SLI Definitions
- Batch availability: successful scheduled runs divided by total scheduled runs.
- Freshness: updates delivered within contracted window.
- Power BI refresh reliability: successful refreshes within target duration.
- Streaming lag: monitored minutes below configured lag threshold.

## Initial SLO Targets
- Tier-1 batch availability: 99.5% monthly.
- Tier-1 freshness compliance: 99.0% monthly.
- Tier-1 Power BI refresh within SLA: 99.0% monthly.

## Alert Catalog Minimum
- Trigger query and threshold.
- Severity and trigger duration.
- Owner and escalation route.
- Runbook URL.
- Dedupe/suppression behavior.

## Day-2 Operational Checklist
- Weekly SLO review with trend reporting.
- Incident postmortems for P1/P2 failures.
- Release-gate evidence retained for audit.
