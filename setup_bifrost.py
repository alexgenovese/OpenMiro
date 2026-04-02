import urllib.request, json

BASE = 'http://localhost:8080/api/providers'

OLLAMA_CONFIG = {
    "network_config": {
        "base_url": "http://openmiro-ollama:11434",
        "default_request_timeout_in_seconds": 300,
    },
    "concurrency_and_buffer_size": {"concurrency": 1000, "buffer_size": 5000},
}

def _call(url, method, body):
    req = urllib.request.Request(
        url,
        method=method,
        headers={'Content-Type': 'application/json'},
        data=json.dumps(body).encode('utf-8'),
    )
    try:
        res = urllib.request.urlopen(req)
        print("OK:", res.read().decode())
    except Exception as e:
        raw = e.read().decode() if hasattr(e, 'read') else str(e)
        data = json.loads(raw)
        if data.get("status_code") == 409:
            # Provider already exists — update it
            print("Provider exists, updating…")
            _call(f"{BASE}/ollama", 'PUT', OLLAMA_CONFIG)
        else:
            print("Error:", raw)


# Register Ollama provider (creates it or updates if already present)
body = {"provider": "ollama", **OLLAMA_CONFIG}
_call(BASE, 'POST', body)
try:
    res = urllib.request.urlopen(req)
    print("Success:", res.read().decode())
except Exception as e:
    print("Error:", e.read().decode() if hasattr(e, 'read') else str(e))
