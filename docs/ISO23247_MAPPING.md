# NetTwin 3.0 — ISO 23247 Digital Twin Framework Mapping

ISO 23247 (Digital twin — Framework for manufacturing) defines a reference
architecture with four core dimensions.  Although the standard is manufacturing
oriented, its structure maps cleanly to NetTwin, a network-security digital
twin.  This document provides the formal mapping used in the NetTwin 3.0
system architecture.

## The Four ISO 23247 Dimensions

| ISO 23247 Dimension | Meaning | NetTwin Abstraction |
|---|---|---|
| **Reference Resources** | Physical & logical assets being twinned | Network entities: nodes, links, interfaces, AWS resources |
| **Reference Activities** | Processes, events and actions on resources | Simulation loop, attack campaigns, response actions, sync ingest |
| **Reference Information** | Data, models and knowledge describing the twin | Topology graph, telemetry history, causal/ML models, alerts |
| **Reference Infrastructure** | Hardware/software/services enabling the twin | NetTwin engine, AWS adapters, dashboard, Terraform infrastructure |

A fifth dimension — **Reference Services / Standards** — is sometimes added in
digital-twin literature; NetTwin maps it to the API surface, evaluation harness
and published research protocols.

---

## 1. Reference Resources

> *“Physical or logical elements of the target system that the digital twin
> represents and monitors.”*

### 1.1 Network entities

| Resource Class | Examples | Code Location |
|---|---|---|
| Compute nodes | `web1`, `app1`, `db1`, `attacker` | `nettwin/simulator/topology.py` |
| Network links | `edge3-web1`, `core1-dist2` | `nettwin/simulator/topology.py` |
| Logical roles | core router, firewall, internet gateway | `nettwin/simulator/topology.py` |
| Real AWS resources | EC2 instances, subnets, security groups | `infra/terraform/`, `nettwin/ingestion/adapters/aws_discovery.py` |

### 1.2 Mapping rules

- Every `Node` and `Link` in `Topology` is a reference resource with a stable
  identifier, type (`kind`) and static attributes (position, bandwidth).
- AWS discovery maps real resources to twin entities via `entity_to_instance`,
  `entity_to_ip`, `entity_to_subnet`, `entity_to_nacl` dictionaries consumed by
  the actuation translator.
- Traffic Mirroring VXLAN packets are parsed into per-flow reference records
  (`src`, `dst`, `proto`, `src_port`, `dst_port`) before normalization.

---

## 2. Reference Activities

> *“Operations, events and control actions performed on or by reference
> resources.”*

### 2.1 Activities in NetTwin

| Activity | Description | Code Location |
|---|---|---|
| **Sense** | Ingest telemetry from simulation, AWS CloudWatch, Flow Logs, Traffic Mirroring | `nettwin/ingestion/`, `nettwin/api/app.py` |
| **Simulate** | Advance the discrete-event network simulator | `nettwin/simulator/engine.py` |
| **Detect** | Score anomalies with ensemble detector + conformal calibration | `nettwin/twin/detector.py`, `nettwin/twin/conformal.py` |
| **Diagnose** | Rank root causes with causal analysis | `nettwin/twin/causal.py`, `eval/baselines.py` |
| **Decide** | Propose and rank response actions via SafeBandit | `nettwin/response/agent.py` |
| **Act** | Translate decisions into AWS changes (SG, NACL, tc, WAF) | `nettwin/actuation/` |
| **Sync** | Promote/demote entities between SIMULATED, SHADOW and HYBRID | `nettwin/ingestion/sync.py` |

### 2.2 Lifecycle state machines

- **Entity sync state machine**: `SIMULATED → SHADOW → HYBRID` (and reverse on
  staleness/divergence) — `nettwin/ingestion/sync.py`.
- **Actuation state machine**: `PENDING → TRANSITIONING → ENFORCED` with failure
  paths to `FAILED` and `ROLLED_BACK` — `nettwin/actuation/executor.py`.

---

## 3. Reference Information

> *“Data, models and knowledge that describe the state, behavior and relations
> of reference resources.”*

### 3.1 Information models

| Information Type | Content | Code Location |
|---|---|---|
| Topology graph | Nodes, links, shortest paths, adjacency | `nettwin/simulator/topology.py` |
| Telemetry history | Per-entity metric buffers (throughput, latency, loss, CPU, memory) | `nettwin/twin/state.py` |
| Anomaly scores | Detector scores, conformal p-values, drift events | `nettwin/twin/detector.py`, `nettwin/twin/drift.py` |
| Causal model | Lagged correlation, onset, centrality ranking | `nettwin/twin/causal.py` |
| Predictive model | Holt-Winster forecasts with conformal intervals | `nettwin/twin/predictor.py` |
| Response knowledge | Bandit posteriors, action history, rewards | `nettwin/response/agent.py`, `bandit_state.json` |
| Alerts & audit | Active/resolved alerts, response action logs | `nettwin/alerts.py`, `nettwin/storage.py` |

### 3.2 Fidelity metrics

The ISO 23247 concept of *twin fidelity* is explicitly modeled in
`EntitySync` via:

- Relative divergence (`divergence_w_rel`)
- Shape/correlation divergence (`divergence_w_corr`)
- Hysteresis-controlled promotion/demotion thresholds

See `nettwin/ingestion/sync.py` and `tests/test_sync.py`.

---

## 4. Reference Infrastructure

> *“Hardware, software, networks and services that enable the digital twin.”*

### 4.1 Runtime infrastructure

| Component | Role | Code / Artifact |
|---|---|---|
| NetTwin engine | Discrete-event simulator + real-time loop | `nettwin/simulator/engine.py`, `nettwin/api/app.py` |
| Ingestion server | UDP syslog/JSON telemetry receiver | `nettwin/ingestion/server.py` |
| AWS adapters | CloudWatch, Flow Logs, Traffic Mirroring | `nettwin/ingestion/adapters/` |
| Storage | SQLite persistence for snapshots/alerts | `nettwin/storage.py` |
| Dashboard | Real-time visualization UI | `dashboard/` |
| Scenario Studio | What-if drill authoring & replay | `studio/` |

### 4.2 Cloud infrastructure

All AWS resources are declared in `infra/terraform/`:

- Dual-region VPCs, subnets, route tables, security groups
- EC2 instances (web1, web2, app1, app2, traffic-gen)
- ALB + AWS WAF v2 + RDS MySQL Free Tier
- VPC Flow Logs → CloudWatch Logs
- S3 Gateway VPC Endpoint ($0 data transfer fees)
- Automated zero-cost teardown via `shutdown.ps1`

---

## 5. Reference Services / Standards (Extended Dimension)

> *“Interfaces, protocols and evaluation standards that govern how the twin is
> consumed and validated.”*

| Service / Standard | NetTwin Realization |
|---|---|
| API surface | REST + WebSocket in `nettwin/api/` |
| Security | API-key/CORS rate limiting in `nettwin/api/security.py` |
| Evaluation reproducibility | `eval/run_all.py`, `eval/runner.py`, 15-seed statistical harness |
| Research protocols | Five paper-specific experiments in `eval/p{1,2,3,4,5}_*.py` |
| Baseline comparisons | Bandit baselines (`eval/baselines.py`) and RCA baselines (`eval/baselines.py`) |

---

## Maturity Ladder Alignment

NetTwin's maturity progression aligns with the descriptive → diagnostic →
predictive → prescriptive ladder referenced in Paper 5:

| Maturity Level | ISO 23247 Emphasis | NetTwin Capability |
|---|---|---|
| **Descriptive** | Reference Resources + Information | Topology, telemetry, dashboards |
| **Diagnostic** | Reference Activities + Information | Anomaly detection, RCA, drift monitoring |
| **Predictive** | Reference Information + Infrastructure | Forecasting, saturation warnings, what-if sandbox |
| **Prescriptive** | Reference Activities + Services | SafeBandit autonomous response, AWS actuation |

---

## Traceability Summary

| ISO 23247 Dimension | Primary Files |
|---|---|
| Reference Resources | `nettwin/simulator/topology.py`, `infra/terraform/`, `nettwin/ingestion/adapters/aws_discovery.py` |
| Reference Activities | `nettwin/simulator/engine.py`, `nettwin/ingestion/sync.py`, `nettwin/response/agent.py`, `nettwin/actuation/` |
| Reference Information | `nettwin/twin/state.py`, `nettwin/twin/detector.py`, `nettwin/twin/causal.py`, `nettwin/twin/predictor.py`, `nettwin/alerts.py` |
| Reference Infrastructure | `nettwin/api/app.py`, `nettwin/ingestion/server.py`, `infra/terraform/`, `dashboard/`, `studio/` |
| Reference Services | `nettwin/api/`, `eval/`, `tests/` |

---

*Document version: 3.0.0 — maintained alongside the NetTwin 3.0 codebase.*
