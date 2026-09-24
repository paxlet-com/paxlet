# Taskand → Paxlet extraction map

The goal is not to rename Taskand. It is to extract small reusable contracts.

| Taskand concept | Paxlet Core / layer |
|---|---|
| `TicketUriProcess.uri` | explicit registry alias of an exported package; action `run` stays separate |
| `TicketUriProcess.depends_on` | `requires` / composition dependency |
| `TicketUriProcess.human_approval` | node policy / grant layer, not Core identity |
| `TicketOutputs.artifacts` | resource/result references |
| `TicketOutputs.completion_receipt` | Paxlet execution receipt |
| catalog / registry | resolver + Registry layer |
| federation handlers | Network layer |
| mesh peer/projection handlers | Network layer |
| planner / orchestrator | Adaptive-system layer |
| MCP / Digital Twin / web | adapters around nodes and higher systems |
| portable runtime controls | production Node security profile |

This separation lets Taskand continue evolving rapidly while independent runtimes implement the small Paxlet contract.

Taskand package hashes and Paxlet package digests are different content contracts.
Export to a separate directory and preserve provenance; never add a manifest to an
active immutable Taskand package. See [LAN assessment](../../docs/taskand-lan.md).
