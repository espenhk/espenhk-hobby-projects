# Data Contracts

This folder stores versioned dataset contracts used for CI validation.

## Contract file naming
- <dataset>.contract.json

## Required top-level keys
- contractVersion
- dataset
- owner
- description
- schema
- keys
- freshness
- qualityChecks

## Notes
- Contract validation is enforced by ci/data-contract-checks.yml.
- Update scripts/contracts/validate_contracts.py when contract format evolves.
