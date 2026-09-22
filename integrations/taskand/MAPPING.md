# Taskand → Paxlet extraction map

The goal is not to rename Taskand. It is to extract small reusable contracts.

| Taskand concept | Paxlet Core / layer |
|---|---|
| `TicketUriProcess.uri` | action/process URI binding |
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
