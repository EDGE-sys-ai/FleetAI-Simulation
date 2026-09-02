import requests
import time
time.sleep(3)
try:
    r = requests.get('http://localhost:5000', timeout=5)
    print('HTTP:', r.status_code, len(r.text), 'chars')
except Exception as e:
    print('Error:', e)