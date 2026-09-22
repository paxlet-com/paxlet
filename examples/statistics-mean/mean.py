import json, sys
payload = json.load(sys.stdin)
values = payload["values"]
if not values:
    print(json.dumps({"error": "values must not be empty"}), file=sys.stderr)
    raise SystemExit(2)
print(json.dumps({"count": len(values), "mean": sum(values) / len(values)}))
