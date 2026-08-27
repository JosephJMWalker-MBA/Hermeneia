# Contributing

Hermeneia is architecture-first.

Before changing code: 1. Read AGENTS.md 2. Read /docs in numerical
order. 3. Justify changes against Constitution and Invariants.

Code follows specification, never the reverse.

## Test Governance

The default automated suite is hermetic:

```bash
PYTHONPATH=. python3 -m pytest -q
```

Default tests remove ambient cloud-provider credentials before collection and
block external network access. Local loopback test/runtime communication remains
allowed.

Intentional live-provider tests must be marked and opted in explicitly:

```python
@pytest.mark.live_provider
```

```bash
PYTHONPATH=. python3 -m pytest -q --live-providers
```

Live-provider tests may consume paid API usage. Do not put credential values in
tests, logs, docs, or diagnostics.
