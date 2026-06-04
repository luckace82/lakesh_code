#!/bin/bash
# Lakesh — GPU/RAM split setup
# 32 layers on NVIDIA GPU, 32 layers on system RAM
# For: 32GB RAM + 6-8GB VRAM
# Note: GPU setup is Linux-only. macOS and Windows users should skip this.

echo ""
echo "  Lakesh — GPU/RAM Split Setup"
echo "  32 layers GPU  |  32 layers RAM"
echo "  ─────────────────────────────────"
echo ""

# Detect OS
OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" != "Linux" ]; then
    echo "  [!] GPU/RAM split is Linux-only."
    echo "      Detected OS: $OS_TYPE"
    echo "      GPU acceleration requires Linux with systemd."
    echo "      You can still use Lakesh on CPU."
    exit 0
fi

sudo mkdir -p /etc/systemd/system/ollama.service.d/

sudo tee /etc/systemd/system/ollama.service.d/split.conf > /dev/null << 'EOF'
[Service]
# 32 layers on GPU, rest on CPU/RAM
Environment="OLLAMA_GPU_LAYERS=32"
# Use system RAM for overflow layers
Environment="OLLAMA_NUM_PARALLEL=1"
# Larger context fits in RAM now
Environment="OLLAMA_NUM_CTX=8192"
# Keep GPU 0 active but not overloaded
Environment="CUDA_VISIBLE_DEVICES=0"
EOF

echo "  [✓] Ollama service config updated (32/32 split)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELFILE_PATH="$SCRIPT_DIR/Modelfile.lakesh"

cat > "$MODELFILE_PATH" << 'EOF'
FROM qwen3:30b

# Split: 32 GPU layers + 32 RAM layers
PARAMETER num_gpu 32
PARAMETER num_thread 8
PARAMETER num_ctx 8192

# Keep responses focused and fast
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1

SYSTEM """You are Lakesh, a local AI coding assistant. Be concise and direct."""
EOF

echo "  [✓] Modelfile written to $MODELFILE_PATH"

echo "  [→] Creating lakesh-split model in Ollama..."
cd "$SCRIPT_DIR"
ollama create lakesh-split -f Modelfile.lakesh

echo "  [✓] lakesh-split model created"

echo ""
echo "  [→] Verifying GPU memory before..."
nvidia-smi --query-gpu=memory.used,memory.free,temperature.gpu \
    --format=csv,noheader 2>/dev/null | \
    while read line; do echo "      $line"; done

echo ""
echo "  [→] Running test inference..."
ollama run lakesh-split "say ok" > /dev/null 2>&1
sleep 2

echo "  [→] GPU memory after loading (should be ~5-6GB, not full):"
nvidia-smi --query-gpu=memory.used,memory.free,temperature.gpu \
    --format=csv,noheader 2>/dev/null | \
    while read line; do echo "      $line"; done

LAKESH_CLI="$SCRIPT_DIR/lakesh"
LAKESH_SRV="$SCRIPT_DIR/lakesh_server.py"

# Swap model name in both files
if [ -f "$LAKESH_CLI" ]; then
    sed -i 's/MODEL.*=.*"qwen3-coder:30b"/MODEL = "lakesh-split"/' "$LAKESH_CLI"
    echo "  [✓] lakesh updated → using lakesh-split"
fi

if [ -f "$LAKESH_SRV" ]; then
    sed -i 's/qwen3-coder:30b/lakesh-split/g' "$LAKESH_SRV"
    echo "  [✓] lakesh_server.py updated → using lakesh-split"
fi

if [ -f "$SCRIPT_DIR/.env" ]; then
    sed -i 's/LAKESH_MODEL=.*/LAKESH_MODEL=lakesh-split/' "$SCRIPT_DIR/.env"
    echo "  [✓] .env updated → using lakesh-split"
fi

echo "  [→] Restarting Ollama service..."
sudo systemctl daemon-reload
sudo systemctl restart ollama
sleep 3

echo ""
echo "  ─────────────────────────────────────────────"
echo "  Done. Split is active:"
echo ""
echo "  GPU  (6-8GB VRAM)  →  32 layers  ~5-6GB used"
echo "  RAM  (32GB)        →  32 layers  ~14-16GB used"
echo "  GPU temp should drop 10-20°C"
echo ""
echo "  Monitor GPU:   watch -n 1 nvidia-smi"
echo "  Check model:   ollama ps"
echo "  Test Lakesh:   lakesh 'hi'"
echo "  ─────────────────────────────────────────────"
echo ""
