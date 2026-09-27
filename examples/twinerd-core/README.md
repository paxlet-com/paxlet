# Twinerd Core Native Paxlet

Addressable native Digital Twin and virtualization capability package.

## Identity

- **URN**: `urn:paxlet:twinerd:core`
- **Version**: `1.0.0`
- **Binding**: `paxlet://twinerd/core`

## Actions

### `inspect`
Inspects host hardware capabilities, CPU model, machine ID, hardware DRM digest, hardware video acceleration, and supported CoW snapshotting engines.

- **Input**: `{}`
- **Output**: JSON object with `cpu_model`, `machine_id`, `hardware_digest`, `anti_debug_integrity`, etc.

### `benchmark`
Executes zero-copy CoW snapshot benchmark comparing legacy Docker/tar vs native Rust Core.

- **Input**: `{"size_mb": 1024}`
- **Output**: JSON object with `speedup_factor`, `speedup_summary`, `rust_total_ms`, etc.

## Execution

```bash
paxlet verify examples/twinerd-core
paxlet run examples/twinerd-core inspect --input '{}'
paxlet run examples/twinerd-core benchmark --input '{"size_mb": 1024}'
```
