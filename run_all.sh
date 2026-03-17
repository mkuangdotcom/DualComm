#!/bin/bash

# =================================================================
# DualComm - Unified Process Launcher
# =================================================================

# Ensure we are in the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 Memulakan DualComm Unified System..."

# 1. Pastikan persekitaran Python sedia
# (Python standalone installed in /Users/kevin/Desktop/DualComm/python)
export PYTHON_PATH="$DIR/python/bin/python3.11"
export VENV_BIN="$DIR/venv/bin"

# 2. Bersihkan proses lama pada port 8000 dan 8080 (mengelakkan 'Address already in use')
echo "🧹 Membersihkan port sedia ada (8000, 8080)..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Fungsi untuk mematikan semua proses apabila menekan Ctrl+C
cleanup() {
    echo -e "\n\n🛑 Menghentikan semua servis..."
    kill $P_BRIDGE_PID $M_AGENT_PID $NODE_PID 2>/dev/null
    exit
}
trap cleanup SIGINT

# 3. Lancarkan Python Logic Bridge (Port 8000)
echo "🐍 [1/3] Memulakan Python Logic Bridge (Port 8000)..."
$VENV_BIN/python -m uvicorn app.main:app --app-dir python_bridge --host 0.0.0.0 --port 8000 --reload > python_bridge.log 2>&1 &
P_BRIDGE_PID=$!

# 4. Lancarkan Node.js Gateway (WhatsApp/Telegram Bridge)
echo "📲 [2/2] Memulakan Node.js Gateway (Terminal Utama)..."
./node_modules/.bin/tsx src/index.ts
NODE_PID=$!

# Jika Node berhenti, hentikan semuanya
cleanup
