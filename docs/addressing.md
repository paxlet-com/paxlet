# Addressing: identity is not location

Paxlet separates **stable identity** from **current location**.

```text
URN                         URI
what is it?                 where/how is it available?
urn:paxlet:science:fasta-gc file:///opt/paxlets/fasta-gc
                            https://lab.example/fasta-gc
```

A registry maps one stable URN to one or more candidate URI bindings. Core 0.1 uses a local JSON registry so the concept is visible without requiring a server.

The reference runtime executes only `file:` locations. HTTP distribution is intentionally left for a network node/registry layer.
