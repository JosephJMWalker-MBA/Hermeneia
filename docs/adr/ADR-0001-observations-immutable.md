# ADR-0001: Observations Are Immutable

Status: Accepted

## Context

Interpretation must never overwrite source material.

## Decision

Observations are append-only, immutable records.

## Consequences

All higher layers derive from a stable substrate.

## Alternatives

Mutable observations were rejected because they corrupt provenance.
