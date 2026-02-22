#!/bin/bash
# Quick test script for KnowMat chat endpoint
set -e
cd "$(dirname "$0")/backend/src"
source ../../.venv/bin/activate 2>/dev/null || true
PYTHON="../../.venv/bin/python"

# Start server in background
$PYTHON chat_server.py &
PID=$!
trap "kill $PID 2>/dev/null" EXIT

# Wait for server
for i in {1..15}; do
  if curl -s http://127.0.0.1:7896/ >/dev/null 2>&1; then
    echo "Server ready."
    break
  fi
  sleep 1
done

# Test chat (uses query_database + predict_alloy_density; DB must be running for full success)
echo "Running chat test: 请给出合金 Inconel 625 的密度"
RESP=$(curl -s -X POST http://127.0.0.1:7896/chat \
  -H "Content-Type: application/json" \
  -d '{"content":"请给出合金 Inconel 625 的密度","convid":"test-1","method":"planning"}' \
  --max-time 120)
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
