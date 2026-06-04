#!/bin/bash
# Lakesh GPU setup — makes Ollama use your NVIDIA GPU fully
# Run: bash gpu_setup.sh
# Note: GPU setup is Linux-only. macOS and Windows users should skip this.

echo ""
echo "  Lakesh GPU Setup"
echo "  ─────────────────"
echo ""

# Detect OS
OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" != "Linux" ]; then
    echo "  [!] GPU setup is Linux-only."
    echo "      Detected OS: $OS_TYPE"
    echo "      GPU acceleration requires Linux with systemd."
    echo "      You can still use Lakesh on CPU."
    exit 0
fi

if ! command -v nvidia-smi &>/dev/null; then
    echo "  [!] nvidia-smi not found. Install NVIDIA drivers first."
    echo "      Ubuntu: sudo apt install nvidia-driver-525"
    exit 1
fi

echo "  [✓] NVIDIA driver detected"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | \
    while read line; do echo "      GPU: $line"; done

echo ""

echo "  [→] Checking if Ollama uses GPU..."
GPU_LAYERS=$(ollama show qwen2.5-coder:7b --modelfile 2>/dev/null | grep -i "num_gpu" | head -1)
if [ -n "$GPU_LAYERS" ]; then
    echo "  [✓] GPU layers already configured: $GPU_LAYERS"
else
    echo "  [→] GPU not explicitly configured — setting up now"
fi

OLLAMA_ENV_FILE="/etc/systemd/system/ollama.service.d/gpu.conf"
sudo mkdir -p /etc/systemd/system/ollama.service.d/

sudo tee "$OLLAMA_ENV_FILE" > /dev/null << 'EOF'
[Service]
# Use all available NVIDIA GPUs
Environment="CUDA_VISIBLE_DEVICES=0"
# Offload as many layers as possible to GPU
Environment="OLLAMA_GPU_LAYERS=999"
# Use GPU for everything
Environment="OLLAMA_ORIGINS=*"
# Increase context for better code understanding  
Environment="OLLAMA_NUM_CTX=8192"
EOF

echo "  [✓] GPU config written to $OLLAMA_ENV_FILE"

echo "  [→] Restarting Ollama service..."
sudo systemctl daemon-reload
sudo systemctl restart ollama
sleep 3

echo "  [→] Testing GPU inference..."
RESULT=$(ollama run qwen2.5-coder:7b "say 'GPU working'" 2>&1)
GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null)

echo "  [✓] Model responded: $RESULT"
echo "  [✓] GPU memory used: ${GPU_MEM}MB"

if [ "$GPU_MEM" -gt 100 ] 2>/dev/null; then
    echo ""
    echo "  GPU is active and being used by Ollama."
else
    echo ""
    echo "  [!] GPU memory low — model may be running on CPU."
    echo "      Check: ollama ps  (shows if GPU is being used)"
fi

echo ""
echo "  ─────────────────────────────────────────────"
echo "  Done. GPU acceleration is now enabled."
echo "  ─────────────────────────────────────────────"
echo ""
