import json, sys
p = json.load(sys.stdin)
gain = p.get("gain", 1.0)
offset = p.get("offset", 0.0)
print(json.dumps({"values": [v * gain + offset for v in p["values"]]}))
