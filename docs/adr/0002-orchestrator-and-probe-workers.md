# 2. Orchestrator + per-region Probe Workers

Date: 2026-06-18

## Status

Superseded by [ADR 0005](0005-scheduled-collection-and-result-sink.md).

The inbound dispatch contract below (Orchestrator → Probe Worker `POST /measure`) is not deployable: locked-down prod/FedRAMP clusters block inbound calls into the worker pod. ADR 0005 inverts the flow — workers self-schedule and push results out through a Result Sink.

## Context

Runs are on-demand: the user selects a Source Region and triggers a Run interactively. Network latency is physical, so a Run for "source = Mumbai" must originate from Mumbai at request time. Spinning up infrastructure per click is too slow for an interactive dashboard.

## Decision

Split the system into one central **Orchestrator** and N **Probe Workers**, one deployed per Source Region.

- The Orchestrator hosts the UI, the Model/region catalog, and the stored Runs.
- Each Probe Worker is a deployed instance of the location-agnostic Probe (see ADR 0001), exposing `POST /measure {model, targets, n}` and returning per-target statistics.
- For an on-demand Run, the Orchestrator makes a direct synchronous HTTP call to the chosen region's Probe Worker and waits for results.
- The Source Region dropdown reflects the set of Probe Workers currently registered/alive.

Adding a Source Region is a deployment action: stand up one more Probe Worker; it registers and appears in the dropdown. No Orchestrator code change.

## Consequences

- Clean seam: Orchestrator owns coordination + persistence; Probe Workers own measurement. They communicate over one small HTTP contract.
- The `POST /measure` contract is the key interface to keep stable; both sides can be tested against an in-memory adapter.
- Synchronous request/response (not a queue) keeps the on-demand path simple; a long Run holds an HTTP connection open. Acceptable because Runs are user-initiated and bounded (N calls, with per-call timeouts).
- Rejected: queue-based dispatch (workers pull jobs). More resilient but more moving parts than an interactive, bounded, on-demand workload needs.
- Rejected: single co-located worker only. Would block the core feature (choosing among multiple source regions) the moment a second source is wanted.
