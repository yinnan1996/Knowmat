#!/bin/bash
# Run KnowMat backend from project root
cd "$(dirname "$0")/backend/src" || exit 1
exec python3 chat_server.py
