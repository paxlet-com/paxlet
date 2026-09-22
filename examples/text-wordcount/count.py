import json, sys
payload = json.load(sys.stdin)
print(json.dumps({"words": len(payload["text"].split())}))
