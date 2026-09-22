import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"message": f"Hello, {payload['name']}!"}))
