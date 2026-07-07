# 1. Location-agnostic Probe, Source Region as data

Date: 2026-06-18

## Status

Accepted

## Context

The dashboard must measure latency "from a source region." Network round-trip time is physical: to measure latency from region X, the measuring code must actually run in region X. We will not necessarily deploy probes in every region on day one (initially we may run from a single place), but we want to add new source regions later without reworking the data model, API, or dashboard.

## Decision

The Probe is built location-agnostic: it takes the Model, Target Endpoint, and credentials as configuration, and reads its own Source Region from an environment variable. Every Sample records `source_region` as a first-class field, even while only one source exists.

Deploying a new source region is therefore just running the same Probe container in that region with a different `SOURCE_REGION` value — no code or schema change.

## Consequences

- Adding source regions later is a deployment change, not a code change.
- The data model and dashboard must treat source as a real dimension from the start (one extra field/filter now).
- Rejected alternative: a single-origin design with no source concept. Simpler today, but erasing the source dimension would force a schema + API + UI rework the moment a second origin is needed.
