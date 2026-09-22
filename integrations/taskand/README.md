# Taskand as the Paxlet showcase

Taskand is intentionally **not** required by Paxlet Core.

It demonstrates higher-order ideas that can sit above the minimal package model:

- addressable URI processes with actors, payloads, dependencies and approval state;
- outputs that include artifacts/results and completion receipts;
- planner/orchestrator/gateway surfaces;
- CLI, MCP, Digital Twin and web interfaces;
- registry, federation and mesh projections;
- deployment/recovery and governance controls.

Recommended relationship:

```text
Paxlet Core ──────────────┐
                         ├─ Taskand reference showcase
Paxlet Node / Network ───┘
```

Do not copy Taskand's whole domain model into Core. Instead, progressively adapt its reusable contracts to Paxlet URNs, manifests, grants and receipts.

## Taskand -> Paxlet Adapter (`adapt.py`)

Convert Taskand `proc.yaml` processes into standard `paxlet.json` manifests:

```bash
# Convert a single process
python integrations/taskand/adapt.py path/to/proc.yaml

# Convert all generated processes in Taskand
python integrations/taskand/adapt.py ../taskand/generated/

# Dry run / validation only
python integrations/taskand/adapt.py ../taskand/generated/ --dry-run
```

