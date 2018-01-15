import json
import requests
data = {'key':'50d6624f41424826807103b1a76a8f6e',
		'info' : '除非我亲吻青蛙大全无法前往',
		'userid' : '123456'}
r = requests.post('http://www.tuling123.com/openapi/api', data=data)
print(r.json())
print(r.json()['text'])