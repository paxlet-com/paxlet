import json, pathlib, sys
payload = json.load(sys.stdin)
sequence = payload.get("sequence")
if not sequence:
    text = pathlib.Path("data/sample.fasta").read_text()
    sequence = "".join(line.strip() for line in text.splitlines() if not line.startswith(">"))
sequence = sequence.upper()
if not sequence:
    print(json.dumps({"error": "empty sequence"}), file=sys.stderr)
    raise SystemExit(2)
gc = sum(1 for base in sequence if base in {"G", "C"})
print(json.dumps({"length": len(sequence), "gc_fraction": gc / len(sequence)}))
