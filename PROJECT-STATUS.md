# Project status after Core 0.1 bootstrap

## Now present

- brand direction and portal (extracted to dedicated repo `www-paxlet-com`)
- Core 0.1 specification
- machine-readable manifest/receipt schemas
- tiny dependency-free Python reference runtime
- CLI for verify / inspect / resolve / run / pack
- local stable-URN resolver
- execution receipts and deterministic package digests
- explicit permissions contract and secret opt-in
- five examples, including science-oriented examples
- unit tests and external CLI conformance runner
- CI workflow
- Taskand integration boundary document

## Intentionally not yet implemented

- cryptographic signing/trust roots
- OS-enforced capability sandbox
- remote HTTP package fetching
- dependency solver/version ranges
- daemonized node
- distributed registry and peer protocol
- replication/content-addressed cache
- organism/planner/evolution/healing contracts

Those belong to Node/Network/Adaptive layers rather than Paxlet Core.
