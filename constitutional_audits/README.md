# Constitutional Audits

This directory contains immutable ratification records for Hermeneia's constitutional compliance.

## Rules

- Records are **never edited after creation**.
- Records are **never deleted**.
- Each new audit cycle **appends a new file**.
- File names follow the pattern: `YYYY-MM-DD-v{constitution_version}-{event}.md`

## When to create a record

A ratification record is created when:

1. A constitutional invariant reaches ✅ status for the first time
2. A new constitution version is ratified
3. A Human Witness session confirms a CI requiring human review (CI-014, CI-015)
4. The P0 exit criterion is fully met

## Record format

See [TEMPLATE.md](TEMPLATE.md) for the required fields.

## Verification domains

| Domain | Verified By | Proves |
|---|---|---|
| Structure | Static analysis | Architectural boundaries cannot be crossed |
| Behavior | Executable tests | Operational correctness at runtime |
| Understanding | Human witnesses | Successful communication to humans |

CI-014 and CI-015 require all three domains before a ratification record may be created.

---

The moment Hermeneia became constitutionally conformant is itself preserved as immutable evidence.
