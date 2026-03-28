import urllib.request
req = urllib.request.Request('http://localhost:8080/api/providers/ollama', method='DELETE')
try:
    urllib.request.urlopen(req)
    print("Deleted ollama")
except Exception as e:
    print(e)
