#!/usr/bin/env python3
"""
Simple HTTP server to serve assets with proper permissions for mic access.

Run this, then use http://localhost:8765/pngtuber-mage.html in OBS.
"""

import http.server
import os
import socketserver

PORT = 8765
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

os.chdir(ASSETS_DIR)

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"Serving assets at http://localhost:{PORT}/")
    print(f"Use http://localhost:{PORT}/pngtuber-mage.html for the PNGtuber")
    print("Press Ctrl+C to stop")
    httpd.serve_forever()
