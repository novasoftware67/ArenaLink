import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from core import target, execute
from app import Bridge, make_server

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_create_and_read(self):
        result = execute(self.root, {'actions': [
            {'op':'mkdir','path':'site'},
            {'op':'write','path':'site/index.html','content':'Bonjour 🟣'},
            {'op':'read','path':'site/index.html'}]})
        self.assertTrue(result['completed'])
        self.assertEqual(result['results'][-1]['result'], 'Bonjour 🟣')
    def test_path_escape(self):
        for name in ['../secret','/etc/passwd','C:/Windows/a','a\\b','.']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                target(self.root, name)
    def test_link_escape(self):
        try:
            (self.root / 'link').symlink_to(self.root.parent, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        with self.assertRaises(ValueError):
            target(self.root, 'link/secret')
    def test_no_implicit_overwrite(self):
        path = self.root / 'file'
        path.write_text('original')
        result = execute(self.root, {'actions':[{'op':'write','path':'file','content':'changed'}]})
        self.assertFalse(result['completed'])
        self.assertEqual(path.read_text(), 'original')
    def test_explicit_overwrite(self):
        (self.root / 'file').write_text('old')
        result = execute(self.root, {'actions':[{'op':'write','path':'file','content':'new','overwrite':True}]})
        self.assertTrue(result['completed'])
        self.assertEqual((self.root / 'file').read_text(), 'new')
    def test_validate_before_writing(self):
        with self.assertRaises(ValueError):
            execute(self.root, {'actions':[{'op':'mkdir','path':'valid'},{'op':'shell','path':'cmd'}]})
        self.assertFalse((self.root / 'valid').exists())
    def test_stop_on_failure(self):
        result = execute(self.root, {'actions':[{'op':'read','path':'missing'},{'op':'mkdir','path':'later'}]})
        self.assertFalse(result['completed'])
        self.assertFalse((self.root / 'later').exists())
    def test_http_auth_and_approval(self):
        bridge = Bridge()
        bridge.workspace = str(self.root)
        server = make_server(bridge, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/actions'
        body = json.dumps({'actions':[{'op':'mkdir','path':'approved'}]}).encode()
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(url,data=body))
            self.assertEqual(error.exception.code, 401)
            def approve():
                item = bridge.pending.get(timeout=3)
                item['result'] = execute(item['root'],item['plan'])
                item['event'].set()
            worker = threading.Thread(target=approve)
            worker.start()
            request = urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+bridge.token,'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=5) as response:
                self.assertTrue(json.load(response)['completed'])
            worker.join()
            self.assertTrue((self.root / 'approved').is_dir())
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    unittest.main()
