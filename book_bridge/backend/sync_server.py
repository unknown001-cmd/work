"""
同步代理服务器：用 TestClient + http.server 绕过 asyncio socketpair 限制
让浏览器可以直接访问 http://localhost:8000/
"""
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from starlette.testclient import TestClient
from main import app

client = TestClient(app)
_lock = threading.Lock()

class ProxyHandler(BaseHTTPRequestHandler):
    def _handle(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}

        with _lock:
            try:
                if method == "GET":
                    resp = client.get(self.path, headers=headers, follow_redirects=True)
                elif method == "POST":
                    resp = client.post(self.path, content=body, headers=headers)
                elif method == "PUT":
                    resp = client.put(self.path, content=body, headers=headers)
                elif method == "DELETE":
                    resp = client.delete(self.path, headers=headers)
                else:
                    self.send_error(405)
                    return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Proxy Error: {e}".encode())
                return

        self.send_response(resp.status_code)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp.content)))
        self.end_headers()
        if resp.content:
            self.wfile.write(resp.content)

    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_PUT(self): self._handle("PUT")
    def do_DELETE(self): self._handle("DELETE")

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), ProxyHandler)
    print("=" * 50)
    print("  书桥 BOOKBRIDGE + AI Agent")
    print("  访问: http://localhost:8000/")
    print("  按 Ctrl+C 停止")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()