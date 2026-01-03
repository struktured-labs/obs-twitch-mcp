#!/usr/bin/env python3
"""
Simple HTTP server that serves recent Twitch chat messages for the overlay.
Reads from the chat log files created by the MCP server.
"""

import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

CHAT_LOG_DIR = Path(__file__).parent / "logs" / "chat"
PORT = 8765

class ChatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # Enable CORS for browser access
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.end_headers()

        if parsed.path == '/chat':
            self.serve_chat(parsed)
        elif parsed.path == '/health':
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.wfile.write(json.dumps({"error": "not found"}).encode())

    def serve_chat(self, parsed):
        params = parse_qs(parsed.query)
        after_id = params.get('after', [''])[0]
        limit = int(params.get('limit', ['20'])[0])

        messages = self.get_recent_messages(limit, after_id)
        response = {"messages": messages}
        self.wfile.write(json.dumps(response).encode())

    def get_recent_messages(self, limit: int, after_id: str) -> list:
        """Get recent messages from today's log file."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = CHAT_LOG_DIR / f"{today}.jsonl"

        if not log_file.exists():
            return []

        messages = []
        found_after = not after_id  # If no after_id, include all

        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Read from end for most recent
                for line in lines[-100:]:  # Check last 100 lines
                    try:
                        msg = json.loads(line.strip())
                        msg_id = msg.get('timestamp', '') + msg.get('username', '')

                        if after_id and msg_id == after_id:
                            found_after = True
                            continue

                        if found_after:
                            messages.append({
                                'id': msg_id,
                                'username': msg.get('username', 'unknown'),
                                'message': msg.get('message', ''),
                                'is_mod': msg.get('is_mod', False),
                                'is_subscriber': msg.get('is_subscriber', False),
                                'is_broadcaster': msg.get('username', '').lower() == 'struktured',
                                'timestamp': msg.get('timestamp', ''),
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading log: {e}")

        return messages[-limit:]

    def log_message(self, format, *args):
        # Suppress default logging
        pass

def main():
    # Ensure log directory exists
    CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    server = HTTPServer(('localhost', PORT), ChatHandler)
    print(f"Chat server running on http://localhost:{PORT}")
    print(f"Reading logs from: {CHAT_LOG_DIR}")
    print("Endpoints:")
    print(f"  GET /chat - Get recent messages")
    print(f"  GET /health - Health check")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == '__main__':
    main()
