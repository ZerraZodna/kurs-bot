#!/usr/bin/env python3
"""Serve static files and proxy /dev/message POSTs to the API backend.

Usage: dev_static_server.py --port 3000 --directory <static_dir> --api-port 8000
"""
import argparse
import http.client
import http.server
import sys


class ProxyingHandler(http.server.SimpleHTTPRequestHandler):
    api_port = 8000

    def do_POST(self):
        # Proxy API calls to the backend
        if self.path.startswith("/dev/message"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""

            # Use loopback explicitly and allow a generous timeout for model calls
            # Increase timeout to accommodate slow local model inference
            conn = http.client.HTTPConnection("127.0.0.1", self.api_port, timeout=160)
            # Forward minimal headers
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            try:
                conn.request("POST", self.path, body, headers)
                resp = conn.getresponse()
                resp_body = resp.read()

                self.send_response(resp.status)
                # Copy Content-Type if present
                if resp.getheader("Content-Type"):
                    self.send_header("Content-Type", resp.getheader("Content-Type"))
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                if resp_body:
                    self.wfile.write(resp_body)
            except Exception as e:
                # Surface backend connectivity issues as 502 for the browser
                msg = f"Backend at http://localhost:{self.api_port} unavailable: {e}"
                payload = msg.encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            self.send_error(501, "Unsupported method ('POST')")


def run(port, directory, api_port):
    handler = ProxyingHandler
    handler.api_port = api_port
    # Serve files from directory
    import os
    os.chdir(directory)
    with http.server.ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Serving HTTP on 0.0.0.0 port {port} (http://0.0.0.0:{port}/) ...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=3000)
    p.add_argument("--directory", required=True)
    p.add_argument("--api-port", type=int, default=8000)
    args = p.parse_args(argv)
    run(args.port, args.directory, args.api_port)


if __name__ == "__main__":
    main(sys.argv[1:])
