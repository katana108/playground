#!/bin/bash
# Sofi startup wrapper — kills any orphaned instances before starting
pkill -f "sofi/src/main.py" 2>/dev/null || true
sleep 1
exec python3 main.py
