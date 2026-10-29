import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(create_app(self.root, False))
        self.id = self.client.get('/api/canvases').json()[0]['id']

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def canvas(self, text):
        return {'version': 1, 'nodes': [{'id':'text-1','type':'text','position':{'x':12,'y':34},'width':360,'data':{'markdown':text}}], 'viewport': {'x':20,'y':30,'zoom':0.8}}

    def test_roundtrip_restart_and_isolation(self):
        other = self.client.post('/api/canvases', json={'name':'研究'}).json()['id']
        self.assertEqual(self.client.put(f'/api/canvases/{self.id}', json=self.canvas('## 中文\n\n- **重点**\n\n```py\nx=1\n```')).status_code, 200)
        with TestClient(create_app(self.root, False)) as restarted:
            result = restarted.get(f'/api/canvases/{self.id}').json()
            self.assertIn('中文', result['nodes'][0]['data']['markdown'])
            self.assertEqual(result['viewport']['zoom'], 0.8)
            self.assertEqual(restarted.get(f'/api/canvases/{other}').json()['nodes'], [])
        self.assertEqual(self.client.patch(f'/api/canvases/{other}', json={'name':'新名字'}).status_code, 200)

    def test_backup_recovery_and_failed_write(self):
        url = f'/api/canvases/{self.id}'
        self.client.put(url, json=self.canvas('第一版'))
        self.client.put(url, json=self.canvas('第二版'))
        path = self.root / 'canvases' / f'{self.id}.json'
        path.write_text('{broken', encoding='utf-8')
        self.assertEqual(self.client.get(url).json()['nodes'][0]['data']['markdown'], '第一版')
        self.assertEqual(self.client.put(url, json=self.canvas('恢复后')).status_code, 200)
        with patch('backend.app.os.replace', side_effect=OSError('disk full')):
            self.assertEqual(self.client.put(url, json=self.canvas('不应覆盖')).status_code, 500)
        self.assertEqual(self.client.get(url).json()['nodes'][0]['data']['markdown'], '恢复后')

    def test_original_image_and_asset_validation(self):
        buffer = io.BytesIO()
        Image.new('RGB', (80,60), 'green').save(buffer, format='PNG')
        raw = buffer.getvalue()
        upload = self.client.post('/api/assets', files={'file':('capture.png', raw, 'image/png')})
        self.assertEqual(upload.status_code, 201)
        image = upload.json()
        self.assertEqual(self.client.get('/api/assets/' + image['asset']).content, raw)
        payload = self.canvas('')
        payload['nodes'].append({'id':'image-1','type':'image','position':{'x':500,'y':0},'width':80,'height':60,'data':{'asset':image['asset']}})
        self.assertEqual(self.client.put(f'/api/canvases/{self.id}', json=payload).status_code, 200)
        payload['nodes'][1]['data']['asset'] = '../index.json'
        self.assertEqual(self.client.put(f'/api/canvases/{self.id}', json=payload).status_code, 422)
        self.assertEqual(self.client.post('/api/assets', files={'file':('bad.png', b'not-image','image/png')}).status_code, 422)

    def test_local_access_and_validation(self):
        self.assertEqual(self.client.post('/api/canvases', json={'name':'x'}, headers={'Origin':'https://example.com'}).status_code, 403)
        self.assertEqual(self.client.get('/api/info', headers={'Host':'evil.example'}).status_code, 403)
        payload = self.canvas('x')
        payload['version'] = 2
        self.assertEqual(self.client.put(f'/api/canvases/{self.id}', json=payload).status_code, 422)

    def test_two_hundred_cards(self):
        payload = self.canvas('研究笔记')
        buffer = io.BytesIO()
        Image.new('RGB', (120,90), 'white').save(buffer, format='PNG')
        asset = self.client.post('/api/assets', files={'file':('capture.png',buffer.getvalue(),'image/png')}).json()['asset']
        payload['nodes'] = [dict(payload['nodes'][0], id=f'card-{i}', position={'x':i%10*400,'y':i//10*250}) for i in range(100)]
        payload['nodes'] += [{'id':f'image-{i}','type':'image','position':{'x':i%10*400,'y':3000+i//10*250},'width':120,'height':90,'data':{'asset':asset}} for i in range(100)]
        self.assertEqual(self.client.put(f'/api/canvases/{self.id}', json=payload).status_code, 200)
        self.assertEqual(len(self.client.get(f'/api/canvases/{self.id}').json()['nodes']), 200)


if __name__ == '__main__':
    unittest.main()
