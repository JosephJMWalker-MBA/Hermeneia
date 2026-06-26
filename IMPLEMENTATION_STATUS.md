# Implementation Status

**Last updated:** 2026-06-26  
**Current tag:** `sprint-002-build-v0.1`

---

## Cognitive Architecture

```
Witness → Explorer → Architect → Artist → Critic → Steward
```

| Role | Status | Notes |
|------|--------|-------|
| Witness (Corpus ingestion) | Complete | PDF → Observations pipeline |
| Explorer (Discovery) | Phase 1 validated | Ephemeral bucketing + speculative interpretations. Clean Gatsby calibration 2026-06-26. |
| Architect (Reconstruction) | Complete | Blueprint + ArchitectPlan |
| Artist (Communication) | Complete | Multi-profile rendering, recursive protocol |
| Critic (Verification) | Complete | Semantic fidelity reporting |
| Steward (Governance) | Complete | StewardDecision, proposed_interpretations promotion |

---

## Publication Infrastructure

```
Build → Coverage → Release → Preservation
```

| Layer | Status | Notes |
|-------|--------|-------|
| Build (`herm build`) | v0.1 — scaffold complete | Manifest → resolve → coverage → compile → build.json. Tag: sprint-002-build-v0.1 |
| Coverage Engine | Planned — Sprint 003 | Reads build.json; measures section requirements before prose generation |
| Release Steward | Planned — Sprint 004 | Automates measurement; keeps judgment human |
| Preservation Layer | Planned — Sprint 005 | Verification first; export second |

---

## Two-Layer Architecture

```
              Hermeneia

     Cognitive Architecture
┌─────────────────────────────────┐
│ Witness                         │
│ Discovery                       │
│ Reconstruction                  │
│ Verification                    │
│ Governance                      │
│ Communication                   │
└─────────────────────────────────┘
               │
               ▼
     Publication Infrastructure
┌─────────────────────────────────┐
│ Build                           │
│ Coverage                        │
│ Release                         │
│ Preservation                    │
└─────────────────────────────────┘
               │
               ▼
     Durable Knowledge Artifact
```

The engineering layer never tries to think. It serves the cognitive layer.
Automation may measure, verify, package, and preserve. It may not decide.

---

## Release Status

| Artifact | Status |
|----------|--------|
| White Paper | RC-2.1 — frozen pending RC-3 conditions |
| Explorer Phase 1 | Ratified 2026-06-26 |
| herm build v0.1 | Tagged 2026-06-26 |
| v1.0 Release Candidate | Pending P0 completion |

## P0 Before v1.0 RC

- [ ] Semantic obligations quality — Architect produces semantic commitments, not lexical tokens
- [ ] Corpus boundary integrity — visible at every interpretive stage
- [ ] Onboarding around investigative framing
- [ ] End-to-end profile verification
- [ ] Coverage Engine (Sprint 003)
- [ ] Live demonstration video
- [ ] Pitch deck
