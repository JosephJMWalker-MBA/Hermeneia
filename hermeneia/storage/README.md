# Storage

The storage layer persists ontology objects.

It must not perform inference or business logic.

Responsibilities:
- Persist canonical objects
- Preserve provenance
- Maintain append-only semantics
- Read/write .herm bundles
