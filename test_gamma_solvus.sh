#!/bin/bash
# Test γ' solvus temperature prediction (no DB needed)
set -e
cd "$(dirname "$0")/backend/src"
source ../../.venv/bin/activate 2>/dev/null || true
PYTHON="../../.venv/bin/python"

$PYTHON chat_server.py &
PID=$!
trap "kill $PID 2>/dev/null" EXIT

for i in {1..15}; do
  if curl -s http://127.0.0.1:7896/ >/dev/null 2>&1; then
    echo "Server ready."
    break
  fi
  sleep 1
done

echo "Testing: γ' solvus - 10% Ti, 20% Al, 70% Ni (user example)"
curl -s -X POST http://127.0.0.1:7896/chat \
  -H "Content-Type: application/json" \
  -d '{"content":"Estimate the γ'\'' solvus temperature of a superalloy with the following composition: 10% Ti, 20% Al, 70% Ni.","convid":"gamma-solvus-1","method":"planning"}' \
  --max-time 120 | python3 -m json.tool 2>/dev/null || cat
