"""Real bridge HTTP requests against an old/mixed deployment regression."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError
from bridge import llm_bridge
from scripts.check_studio_deployment import check


class OldBackend(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.send_header('Content-Type','text/html')
        self.end_headers()
        self.wfile.write(b'<!doctype html><h1>Not Found</h1>')

    def log_message(self,*args):
        pass


class StudioDeployment(unittest.TestCase):
    def test_old_flask_html_becomes_json_and_deployment_check_fails(self):
        old=ThreadingHTTPServer(('127.0.0.1',0),OldBackend)
        bridge=ThreadingHTTPServer(('127.0.0.1',0),llm_bridge.Handler)
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (old,bridge)]
        for thread in threads:thread.start()
        try:
            with patch.object(llm_bridge,'TOKEN','qa-only'),patch.dict('os.environ',{'BACKEND_PORT':str(old.server_port)}):
                base=f'http://127.0.0.1:{bridge.server_port}'
                with self.assertRaises(HTTPError) as result:urlopen(base+'/backend/api/studio/status?token=qa-only')
                error=result.exception
                self.assertEqual(error.code,404);self.assertIn('application/json',error.headers['Content-Type'])
                self.assertEqual(json.loads(error.read())['error'],'API route unavailable');error.close()
                failures=check(base,'qa-only')
                self.assertEqual(len(failures),1);self.assertIn('Studio backend not ready',failures[0])
                with urlopen(base+'/studio') as response:html=response.read().decode()
                self.assertLess(html.index('window.__FIGG_TOKEN'),html.index('function cardReady'))
                self.assertIn('/js/cards-studio.js?v=studio-2',html)
        finally:
            for server in (bridge,old):server.shutdown();server.server_close()
            for thread in threads:thread.join(timeout=2)
