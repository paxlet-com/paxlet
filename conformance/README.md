# Paxlet Core 0.1 conformance

Run against the included reference CLI:

```bash
python conformance/run.py
```

Run against another implementation exposing the same CLI surface:

```bash
PAXLET_CLI="my-paxlet" python conformance/run.py
```

This first suite intentionally checks only the small Core contract: validation, inspection, JSON action execution, URN resolution and path-safety rejection.
