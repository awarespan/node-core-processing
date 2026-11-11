#!/bin/bash
# ─── SIP Pi Startup Script ────────────────────────────────────────────────────
# Run on boot (via cron @reboot or systemd). Handles:
# 1. Cloudflare Tunnel for stable public URL (no static IP needed)
# 2. MQTT client init
# 3. edge_server startup
# 4. Replays any queued offline incidents

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/edge-ai/logs}"
TUNNEL_LOG="$LOG_DIR/tunnel.log"
EDGE_LOG="$LOG_DIR/edge.log"
QUEUE_LOG="$LOG_DIR/queue.log"

mkdir -p "$LOG_DIR"
cd "$SCRIPT_DIR"

echo "[$(date)] SIP Pi starting up..."

# ─── Load environment ─────────────────────────────────────────────────────────
if [ -f "$HOME/edge-ai/.env" ]; then
    export $(grep -v '^#' "$HOME/edge-ai/.env" | xargs)
    echo "[$(date)] Loaded .env"
else
    echo "[$(date)] WARNING: $HOME/edge-ai/.env not found — using defaults"
fi

# ─── 1. Cloudflare Tunnel ─────────────────────────────────────────────────────
# Installs cloudflared if missing, starts tunnel to port 8766
start_tunnel() {
    local TUNNEL_PORT="${CLOUDFLARE_TUNNEL_PORT:-8766}"
    local TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"

    if command -v cloudflared &>/dev/null; then
        echo "[$(date)] cloudflared found"
    else
        echo "[$(date)] Installing cloudflared..."
        curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
            -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
    fi

    if [ -n "$TUNNEL_TOKEN" ]; then
        # Named tunnel (requires cloudflare account setup)
        cloudflared tunnel --token "$TUNNEL_TOKEN" run >> "$TUNNEL_LOG" 2>&1 &
        echo "[$(date)] Cloudflare Tunnel started (named tunnel)"
    else
        # Quick tunnel (no account needed — generates random trycloudflare.com URL)
        cloudflared tunnel --url "http://localhost:$TUNNEL_PORT" >> "$TUNNEL_LOG" 2>&1 &
        echo "[$(date)] Cloudflare Quick Tunnel started (check $TUNNEL_LOG for URL)"
    fi
}

# ─── 2. MQTT Client (runs in background via event_queue) ──────────────────────
# Started by edge_server.py when Python imports event_queue

# ─── 3. edge_server ───────────────────────────────────────────────────────────
echo "[$(date)] Starting edge_server..."
python3 edge_server.py \
    --host 0.0.0.0 \
    --port "${EDGE_PORT:-8766}" \
    --model "${YOLO_MODEL:-yolov8n.pt}" \
    --imgsz "${YOLO_IMGSZ:-640}" \
    --conf "${YOLO_CONF:-0.4}" \
    --config config.json \
    >> "$EDGE_LOG" 2>&1 &

EDGE_PID=$!
echo "[$(date)] edge_server started (PID=$EDGE_PID)"

# Wait briefly and check if it's alive
sleep 3
if ! kill -0 $EDGE_PID 2>/dev/null; then
    echo "[$(date)] ERROR: edge_server failed to start. Check $EDGE_LOG"
    cat "$EDGE_LOG"
    exit 1
fi

echo "[$(date)] SIP Pi fully started. Dashboard: ws://localhost:${EDGE_PORT:-8766}"
echo "[$(date)] Tunnel URL: check $TUNNEL_LOG"

# ─── 4. Queue replay on startup (process any pending offline incidents) ────────
python3 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath("${SCRIPT_DIR}")))
try:
    import event_queue
    event_queue.start(heartbeat_interval=30)
    print('Backend sync initialized')
    import time; time.sleep(5)
    event_queue.stop()
    print('Queue replay complete')
except ImportError:
    print('event_queue not available — skipping')
except Exception as e:
    print(f'Queue replay error: {e}')
" >> "$QUEUE_LOG" 2>&1 || true

# ─── Keep tunnel running ───────────────────────────────────────────────────────
wait