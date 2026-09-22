# A Paxlet manifest, line by line

Start with five questions:

1. **What am I?** → `identity`
2. **What can I do?** → `actions`
3. **What files travel with me?** → `resources`
4. **What else do I need?** → `requires`
5. **What access do I request?** → `permissions`

```json
{
  "paxlet": "0.1",
  "identity": {
    "urn": "urn:paxlet:example:hello",
    "name": "hello",
    "version": "1.0.0"
  },
  "actions": {
    "hello": {
      "runtime": {"type": "python", "entry": "hello.py"},
      "input": {"type": "object"},
      "output": {"type": "object"}
    }
  },
  "resources": [],
  "requires": [],
  "permissions": {
    "filesystem": {"read": [], "write": []},
    "network": [],
    "secrets": []
  }
}
```

The important idea is not the JSON. The important idea is that another node can inspect the package **before running it**.
