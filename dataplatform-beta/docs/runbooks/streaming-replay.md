# Runbook: Streaming Replay

## Trigger
- Streaming lag breach or data loss/duplication requires replay.

## Preconditions
- Confirm replay window and impact scope.
- Confirm checkpoint path and destination table.

## Replay Procedure
1. Pause affected consumer workflow.
2. Snapshot current checkpoint metadata for audit.
3. Set replay source boundary (offset/time).
4. Run replay pipeline in bounded window mode.
5. Run deduplication and quality checks.
6. Resume standard streaming execution.

## Validation
- Freshness back within target window.
- Duplicate and null-rate checks pass.
- Downstream Gold table contract checks pass.

## Evidence to Capture
- Replay window and source boundary.
- Records processed and rejected counts.
- Validation outputs and operator sign-off.
