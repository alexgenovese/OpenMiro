import urllib.request, urllib.error, json
req = urllib.request.Request(
    'http://localhost:8080/v1/chat/completions', 
    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer dummy'}, 
    data=json.dumps({'model': 'llama3', 'messages': [{'role': 'user', 'content': 'test'}]}).encode('utf-8')
)
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print(e.read().decode())
