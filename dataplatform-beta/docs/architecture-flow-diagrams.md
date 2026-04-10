# Dataplatform Beta Architecture and Flow Diagrams

These diagrams are concise Mermaid sources intended for README and docs usage.

## 1) High-level Azure platform architecture

```mermaid
flowchart LR
  subgraph Sources[Source Systems]
    S1[Operational DBs]
    S2[SaaS APIs]
    S3[Files and Events]
  end

  subgraph Azure[Azure Platform]
    EH[Event Hubs]
    AL[Databricks Auto Loader]
    DBX[Azure Databricks]
    FDRY[Azure AI Foundry]
    UC[Unity Catalog]
    ADLS[ADLS Gen2\nDelta Lake]
    KV[Key Vault]
    LA[Log Analytics and Alerts]
    ENTRA[Entra ID Groups]
  end

  subgraph BI[Power BI]
    WS[Dev/Test/Prod Workspaces]
    PIPE[Deployment Pipeline\nDev -> Test -> Prod]
    USERS[Business Consumers]
  end

  S1 --> AL
  S2 --> AL
  S3 --> EH
  EH --> DBX
  AL --> DBX
  DBX <--> ADLS
  UC -. governance and lineage .- DBX
  KV -. secrets and connection contract .- DBX
  KV -. connection contract .- FDRY
  ENTRA -. RBAC .- UC
  DBX --> FDRY
  DBX --> WS
  WS --> PIPE
  PIPE --> USERS
  DBX --> LA
  FDRY --> LA
  WS --> LA
```

## 2) Data flow: medallion + orchestration + Power BI

```mermaid
flowchart LR
  SRC[Batch Files and Event Streams] --> RAW[Raw\nImmutable Landing]
  RAW --> BRONZE[Bronze\nStandardized Delta]
  BRONZE --> SILVER[Silver\nValidated and Conformed]
  SILVER --> GOLD[Gold\nStar Schemas and Data Marts]
  GOLD --> FX[foundry-exchange\nApproved Gold Publish]

  BRONZE --> Q[Quarantine\nInvalid Records + Reason Codes]
  SILVER --> Q

  ORCH[Databricks Workflows\nSchedules + Job Dependencies] -. orchestrates .-> RAW
  ORCH -. orchestrates .-> BRONZE
  ORCH -. orchestrates .-> SILVER
  ORCH -. orchestrates .-> GOLD
  ORCH -. publish step .-> FX

  UC[Unity Catalog External Location] -. governs .-> FX
  KV[Key Vault Connection Contract] -. connects .-> FX
  FX --> FDRY[Azure AI Foundry]

  GOLD --> SM[PBIP Semantic Models]
  SM --> RPT[Thin Reports]
  RPT --> CON[Business Consumers]

  REF[Dataset Refresh + Smoke Checks] -. validates .-> SM
```

## 3) CI/CD promotion flow: PBIP and Terraform

```mermaid
flowchart TD
  DEV[Developer Change] --> PR[Pull Request]

  subgraph PBIP[PBIP Path]
    PR --> PBIP_CI[CI: powerbi-pr-validation\nvalidate_pbip.py]
    PBIP_CI --> MERGE[Merge to main]
    MERGE --> REL[powerbi-release: publish-dev]
    REL --> DEV_SMOKE[Dev smoke checks]
    DEV_SMOKE --> PROMOTE_TEST[Promote Dev -> Test]
    PROMOTE_TEST --> TEST_SMOKE[Test smoke checks]
    TEST_SMOKE --> PROD_GATE[Manual dispatch + change ticket]
    PROD_GATE --> PROMOTE_PROD[Promote Test -> Prod]
    PROMOTE_PROD --> PROD_SMOKE[Prod smoke checks]
  end

  subgraph TF[Terraform Path]
    PR --> TF_PLAN[PR checks: fmt and validate and plan]
    TF_PLAN --> TF_MERGE[Merge to main]
    TF_MERGE --> APPLY_DEV[Apply dev environment]
    APPLY_DEV --> APPLY_TEST[Apply test after approval]
    APPLY_TEST --> APPLY_PROD[Apply prod after approval]
  end

  PROD_SMOKE --> EVIDENCE[Deployment Evidence\nrun id, approver, timestamp]
  APPLY_PROD --> EVIDENCE
```

## 4) Example Databricks Asset Bundle workflow

```mermaid
flowchart LR
  SRC[Orders CSV + FX CSV] --> RAW[raw\nPython task]
  RAW --> BRONZE[bronze\nPython task]
  BRONZE --> SILVER[silver\nPython task]
  SILVER --> GOLD[gold\nPython task]
  GOLD --> PUBLISH[publish_approved_gold\nPython task]
  PUBLISH --> FX[foundry-exchange]
  GOLD --> BI[Power BI import path]
  FX --> FDRY[Azure AI Foundry]
```
