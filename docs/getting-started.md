# Getting started in five minutes

```bash
./bin/paxlet init /tmp/my-first
./bin/paxlet run /tmp/my-first hello --input '{"name":"Ada"}'

./bin/paxlet verify examples/hello
./bin/paxlet inspect examples/hello
./bin/paxlet run examples/hello hello --input '{"name":"Ada"}'

./bin/paxlet resolve urn:paxlet:example:hello
./bin/paxlet run urn:paxlet:example:hello hello --input '{"name":"Lin"}'
```

Then try a scientific capability:

```bash
paxlet run examples/science-fasta-gc analyze --input '{}'
```

The action reads the included FASTA resource and returns JSON. A receipt is written next to the example.
