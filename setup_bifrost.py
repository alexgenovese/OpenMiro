import urllib.request, json
req = urllib.request.Request(
    'http://localhost:8080/api/providers', 
    headers={'Content-Type': 'application/json'}, 
    data=json.dumps({
        "provider": "ollama",
        "network_config": {
            "base_url": "http://openmiro-ollama:11434"
        }
    }).encode('utf-8')
)
try:
    res = urllib.request.urlopen(req)
    print("Success:", res.read().decode())
except Exception as e:
    print("Error:", e.read().decode() if hasattr(e, 'read') else str(e))
