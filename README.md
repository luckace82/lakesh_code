# Lakesh — Local AI Coding Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/Ollama-Supported-green.svg)](https://ollama.com)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg)](https://github.com/luckace82/lakesh_code)

Lakesh is a sophisticated local AI coding assistant that runs entirely on your machine using Ollama. It provides intelligent code analysis, file operations, and conversational assistance through both a CLI interface and an HTTP server.

## What is Lakesh?

Lakesh is a complete AI-powered development assistant that combines:
- **Intent-based routing**: Automatically detects when you need file access vs. simple conversation
- **Tool execution**: Read files, search code, run commands, write files, and manage memory
- **Semantic search**: ChromaDB-powered codebase understanding
- **Dual interface**: Interactive CLI and HTTP server with OpenAI-compatible API
- **GPU optimization**: Configurable GPU/RAM split for better performance on resource-constrained systems

## How It Works

<details>
<summary><strong>Architecture Overview (click to expand)</strong></summary>

```
User Input → Intent Classifier → Route Decision
                                    ↓
                         ┌─────────┴─────────┐
                         ↓                   ↓
                    Chat Path            Agent Path
                    (No tools)          (With tools)
                         ↓                   ↓
                    Direct Model        Tool Loop
                    Response            → Read/Search/Run
                                        → Model Response
                                        → Final Answer
```
</details>

<details>
<summary><strong>Intent Classification (click to expand)</strong></summary>

Before any model call, Lakesh analyzes your input using:
- **Filename patterns**: Detects `server.py`, `views.js`, `config.yaml` via regex
- **Action keywords**: analyze, review, fix, edit, search, refactor, debug, etc.
- **File references**: file, folder, directory, .py, .js, .ts, etc.
- **Pure greetings**: hi, hello, thanks, bye → always chat path

This routing happens with **zero model latency** - it's pure string matching.
</details>

<details>
<summary><strong>Agent Workflow (click to expand)</strong></summary>

When the agent path is triggered:
1. **System prompt** instructs the model to NEVER ask for code pasting
2. **Model responds** with analysis or a `TOOL_CALL` JSON
3. **Tool execution**:
   - `list_dir(path)` - Find files
   - `read_file(path)` - Read content
   - `search_code(query)` - Semantic search
   - `run_command(cmd)` - Execute commands
   - `write_file(path, content)` - Create/edit files
4. **Tool result** fed back to model
5. **Final response** in markdown with code blocks
</details>

## Tools Available

<details>
<summary><strong>File System Tools (click to expand)</strong></summary>

#### `read_file(path)`
- **Purpose**: Read any file from disk
- **Usage**: Automatically called when filename is mentioned
- **Truncation**: Files >6000 chars truncated with `[... truncated...]` marker
- **Error handling**: Returns error message if file not found

#### `list_dir(path=".")`
- **Purpose**: List directory contents
- **Usage**: Used to find file paths before reading
- **Output**: Sorted list with `/` suffix for directories
- **Default**: Current directory if no path specified

#### `write_file(path, content)`
- **Purpose**: Create or edit files
- **Features**: Auto-creates parent directories
- **Error handling**: Returns success or error message
</details>

<details>
<summary><strong>Command Execution (click to expand)</strong></summary>

#### `run_command(cmd)`
- **Purpose**: Execute shell commands
- **Timeout**: 30 seconds max
- **Output limit**: 2000 characters
- **Working directory**: Current project directory
- **Combined output**: stdout + stderr
</details>

<details>
<summary><strong>Code Search (click to expand)</strong></summary>

#### `search_code(query)`
- **Purpose**: Semantic search across indexed codebase
- **Technology**: ChromaDB + nomic-embed-text embeddings
- **Results**: Top 4 matches with file paths and content snippets
- **Prerequisite**: Must run `python indexer.py` first
- **Index location**: `.chroma/` directory
</details>

<details>
<summary><strong>Memory System (click to expand)</strong></summary>

#### `memory_get(key)`
- **Purpose**: Recall saved notes
- **Storage**: `.lakesh_memory.json` in project root
- **Format**: `{"key": {"value": "...", "saved": "ISO-8601-timestamp"}}`

#### `memory_set(key, value)`
- **Purpose**: Save notes for later recall
- **Persistence**: JSON file in project directory
- **Use cases**: Remembering user preferences, project context, etc.
</details>

## Configuration

### Important: Path Configuration

Lakesh scripts use relative paths and will work on any system. The GPU setup scripts automatically detect the project directory. No manual path configuration is required.

### Environment Variables (.env)

```env
# Mode Selection
LAKESH_MODE=agent              # "agent" (full tools) or "chat" (no tools)

# Agent Configuration
LAKESH_AGENT_NAME=Lakesh       # Agent name used in system prompts

# Model Configuration
LAKESH_MODEL=qwen3-coder:30b  # Ollama model to use (any model supported by Ollama)
LAKESH_MAX_STEPS=10           # Max agent loop iterations

# Server Configuration
LAKESH_PORT=8765              # HTTP server port
```

### Mode Differences

| Feature | Agent Mode | Chat Mode |
|---------|-----------|-----------|
| File reading | ✅ | ❌ |
| Code search | ✅ | ❌ |
| Command execution | ✅ | ❌ |
| File writing | ✅ | ❌ |
| Memory tools | ✅ | ✅ |
| Speed | Slower (tool overhead) | Faster (direct model) |
| Use case | Code analysis, debugging | General questions, explanations |

## Installation

### Prerequisites

1. **Ollama** (AI model runtime)
2. **Python 3.8+**
3. **NVIDIA GPU** (optional, for acceleration)

### Linux Installation

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models (qwen3-coder:30b recommended for coding, but any Ollama model works)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Navigate to project
cd /path/to/codeanalyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env as needed

# Run CLI
./lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

### Making Lakesh Globally Available

To use `lakesh` from any directory without typing the full path:

```bash
# Copy to a directory in your PATH
sudo cp lakesh /usr/local/bin/lakesh
# OR for user-level installation (no sudo needed)
mkdir -p ~/.local/bin
cp lakesh ~/.local/bin/lakesh

# Make it executable
chmod +x ~/.local/bin/lakesh

# Add ~/.local/bin to PATH if not already there
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
# OR for zsh:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# Reload your shell
source ~/.bashrc  # or source ~/.zshrc

# Now you can run lakesh from anywhere
lakesh
```

**Verify installation:**
```bash
which lakesh
# Should show: /usr/local/bin/lakesh or /home/username/.local/bin/lakesh

lakesh --help
# Should show usage information
```

### macOS Installation

```bash
# Install Ollama
brew install ollama

# Pull models (qwen3-coder:30b recommended for coding, but any Ollama model works)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Navigate to project
cd /path/to/codeanalyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env

# Run CLI
./lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

### Making Lakesh Globally Available on macOS

To use `lakesh` from any directory without typing the full path:

```bash
# Copy to a directory in your PATH
sudo cp lakesh /usr/local/bin/lakesh
# OR for user-level installation (no sudo needed)
mkdir -p ~/.local/bin
cp lakesh ~/.local/bin/lakesh

# Make it executable
chmod +x ~/.local/bin/lakesh

# Add ~/.local/bin to PATH if not already there
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc

# Reload your shell
source ~/.zshrc

# Now you can run lakesh from anywhere
lakesh
```

**Verify installation:**
```bash
which lakesh
# Should show: /usr/local/bin/lakesh or /Users/username/.local/bin/lakesh

lakesh --help
# Should show usage information
```

### Windows Installation

```powershell
# Install Ollama from https://ollama.com/download

# Pull models (qwen3-coder:30b recommended for coding, but any Ollama model works)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Navigate to project
cd C:\path\to\codeanalyzer

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
copy .env.example .env

# Run CLI
python lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

## Platform-Specific Features

### GPU Acceleration (Linux Only)

GPU acceleration via NVIDIA CUDA is **Linux-only** due to systemd dependency for Ollama service configuration.

**Linux with NVIDIA GPU:**
- Run `bash gpu_setup.sh` for full GPU acceleration
- Run `bash gpu_ram_split.sh` for GPU/RAM split configuration
- Requires NVIDIA drivers and CUDA

**macOS / Windows:**
- GPU setup scripts will detect non-Linux OS and exit gracefully
- Lakesh will run on CPU only
- All other features work normally

### File Watcher (All Platforms)

The file watcher (`watcher.py`) uses the `watchdog` library and works on:
- Linux
- macOS
- Windows

### System Commands

The `run_command` tool executes shell commands and works on all platforms, but command syntax may vary:
- Linux/macOS: Bash commands
- Windows: PowerShell or CMD commands

### Path Handling

All scripts use relative paths and automatically detect the project directory. No manual path configuration required on any platform.

## Usage

### CLI (Interactive Mode)

```bash
# Start interactive session
lakesh

# Commands within CLI:
# - clear: Reset conversation context
# - memory: View saved memories
# - cd <path>: Change directory
# - exit: Quit

# Single task (non-interactive)
lakesh "analyze the server.py file"
lakesh "fix the authentication bug"
lakesh "explain how the database works"

# Specify model
lakesh --model llama3:8b "what is this code doing?"
```

### HTTP Server

```bash
# Start server
uvicorn lakesh_server:app --port 8765

# Health check
curl http://localhost:8765/health

# Run task (sync)
curl -X POST http://localhost:8765/run \
  -H "Content-Type: application/json" \
  -d '{"task": "list files", "history": []}'

# Stream response
curl -X POST http://localhost:8765/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "explain main.py", "history": []}'
```

### OpenAI-Compatible API

The server provides OpenAI-compatible endpoints for IDE integration:

```bash
# Chat completions
curl -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'

# List models
curl http://localhost:8765/v1/models
```

**Continue.dev Configuration:**

To use Lakesh with the Continue.dev VS Code extension:

1. **Start the Lakesh server:**
   ```bash
   uvicorn lakesh_server:app --port 8765
   ```

2. **Open Continue.dev settings in VS Code:**
   - Press `Cmd/Ctrl + Shift + P`
   - Search for "Continue: Configuration"
   - Or open settings and search for "Continue"

3. **Add Lakesh as an OpenAI-compatible provider:**
   ```json
   {
     "apiBase": "http://localhost:8765/v1",
     "title": "Lakesh",
     "apiKey": "ollama",
     "models": [
       {
         "id": "qwen3-coder:30b",
         "name": "Lakesh (qwen3-coder:30b)",
         "maxContext": 8192,
         "provider": "openai"
       }
     ]
   }
   ```

4. **Select Lakesh in Continue.dev:**
   - Click the model selector in the Continue.dev sidebar
   - Choose "Lakesh" from the dropdown
   - Start chatting with your codebase

**Available Tools in Continue.dev:**

Lakesh exposes the following tools via the `/v1/tools` endpoint:
- `read_file(path)` - Read file contents
- `list_dir(path)` - List directory contents
- `write_file(path, content)` - Write to files
- `run_command(cmd)` - Execute shell commands
- `search_code(query)` - Semantic code search

Continue.dev can automatically call these tools when you ask it to read files, run commands, or search your codebase.

**Note:** The Lakesh server provides an OpenAI-compatible API at `/v1/chat/completions` with tool support at `/v1/tools`, making it work seamlessly with Continue.dev and other OpenAI-compatible tools.

### Codebase Indexing

For semantic search across your codebase:

```bash
# Index current directory
python indexer.py

# Index specific path
python indexer.py /path/to/project

# Index is saved to .chroma/ directory
# Run once per project or after major changes
```

### GPU Optimization

For systems with limited GPU memory:

```bash
# Run GPU/RAM split setup
bash gpu_ram_split.sh

# This creates a custom model with:
# - 32 layers on GPU (~5-6GB VRAM)
# - 32 layers on RAM (~14-16GB system RAM)
# - Reduces GPU temperature by 10-20°C

# After setup, update .env:
LAKESH_MODEL=lakesh-split
```

## Project Structure

```
codeanalyzer/
├── lakesh                  # Main CLI script
├── lakesh_server.py        # HTTP server with OpenAI API
├── indexer.py              # Codebase semantic indexer
├── gpu_ram_split.sh        # GPU/RAM split configuration
├── gpu_setup.sh            # Basic GPU configuration
├── .env                    # Configuration file
├── .lakesh_memory.json     # Persistent memory (auto-generated)
├── .chroma/                # Vector database (auto-generated)
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── analyzer/               # Code analysis tools
    ├── parser.py           # AST-based code parser
    └── extractor.py        # Graph structure builder
```

## Technical Details

### Intent Classifier Algorithm

```python
def needs_agent(task: str) -> bool:
    # 1. Check mode override
    if MODE == "chat":
        return False
    
    # 2. Pure greetings → chat only
    if task in CHAT_ONLY:
        return False
    
    # 3. Filename pattern (e.g., server.py) → agent
    if regex.search(r'\b\w+\.\w{1,5}\b', task):
        return True
    
    # 4. Agent keywords → agent
    if any(keyword in task for keyword in AGENT_KEYWORDS):
        return True
    
    # 5. Default → chat
    return False
```

### Agent Loop Logic

```
for step in range(MAX_STEPS):
    1. Get model response (streaming)
    2. Parse for TOOL_CALL JSON
    3. If no tool call → return response
    4. Execute tool
    5. Display result in panel (if >200 chars)
    6. Feed result back to model
    7. Continue loop
```

### System Prompts

**Chat System Prompt:**
```
You are Lakesh, a friendly local AI coding assistant.
Be concise and direct. For greetings, simple questions, or anything 
that does NOT need file access — answer directly without using any tools.
```

**Agent System Prompt:**
```
You are Lakesh, a senior software engineer AI assistant with direct 
access to the filesystem.

CRITICAL RULES:
1. NEVER ask the user to paste or share file contents. You have read_file — use it.
2. If the user mentions a filename (e.g. server.py), ALWAYS call read_file on it immediately.
3. If you don't know the exact path, call list_dir first to find it, then read_file.
4. Only after reading the file should you analyse or respond about it.
```

## Dependencies

### Python Packages
- `ollama>=0.1.0` - Ollama Python client
- `fastapi>=0.104.0` - HTTP server framework
- `uvicorn>=0.24.0` - ASGI server
- `rich>=13.0.0` - Terminal UI
- `chromadb>=0.4.0` - Vector database
- `python-dotenv>=1.0.0` - Environment configuration

### System Requirements
- **Ollama**: AI model runtime
- **NVIDIA GPU**: Optional, for CUDA acceleration
- **RAM**: 16GB+ recommended (32GB for GPU/RAM split)
- **VRAM**: 6-8GB for full GPU, 4GB for split mode

### Ollama Models
- **Primary**: `qwen3-coder:30b` (18GB) - Coding specialist (recommended)
- **Alternative**: `lakesh-split` (custom) - GPU/RAM split version
- **Other options**: Any Ollama model (llama3, mistral, codellama, etc.)
- **Embedding**: `nomic-embed-text` (274MB) - For semantic search

## Troubleshooting

### Model not found
```bash
# Check available models
ollama list

# Pull the model (any Ollama model works)
ollama pull qwen3-coder:30b
```

### GPU not being used
```bash
# Check NVIDIA driver
nvidia-smi

# Run GPU setup
bash gpu_setup.sh

# Or run split setup
bash gpu_ram_split.sh
```

### Import errors
```bash
# Install missing dependencies
pip install -r requirements.txt
```

### Port already in use
```bash
# Change port in .env
LAKESH_PORT=8766

# Or kill existing process
pkill -f uvicorn
```

### Search unavailable
```bash
# Index the codebase first
python indexer.py

# Check ChromaDB directory
ls -la .chroma/
```

### Agent not using tools
```bash
# Check mode in .env
LAKESH_MODE=agent

# Verify intent classifier is working
# The task should contain agent keywords or filename patterns
```

## Performance Tips

1. **Use Chat Mode** for general questions - faster response
2. **Index codebase** once per project for semantic search
3. **GPU/RAM split** reduces GPU memory usage and temperature
4. **Limit history** - CLI keeps last 20 messages
5. **Truncate files** - Large files automatically truncated to 6000 chars

## Security Considerations

- **File access**: Agent can read/write any file in accessible directories
- **Command execution**: `run_command` can execute any shell command
- **No sandboxing**: Currently runs with same permissions as user
- **Recommendation**: Use in trusted environments only

## Future Improvements

See README.md "Suggestions for Improvement" section for detailed roadmap including:
- Performance optimizations (caching, quantization)
- New features (git integration, test generation, refactoring)
- UX improvements (web UI, VS Code extension, voice input)
- Security enhancements (sandboxing, path restrictions, audit logging)
- Architecture improvements (plugin system, model switching)

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.

## Features

- 🚀 **Fast Path**: Intelligent routing between chat and agent modes
- 🔧 **Tools**: Read files, list directories, write files, run commands, search code
- 🧠 **Semantic Search**: ChromaDB-powered codebase search
- 💾 **Memory**: Persistent context storage
- 🎨 **Rich UI**: Beautiful terminal output with Rich library
- 🌐 **HTTP Server**: OpenAI-compatible API for IDE integration
- ⚡ **GPU Acceleration**: NVIDIA CUDA support via Ollama

## Quick Start

### Prerequisites

1. **Ollama** (required for AI models)
2. **Python 3.8+**
3. **NVIDIA GPU** (optional, for acceleration)

### Installation

#### Linux

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (any Ollama model works - qwen3-coder:30b recommended for coding)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Clone or navigate to project
cd /path/to/codeanalyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# or manually:
pip install ollama fastapi uvicorn rich chromadb python-dotenv

# Configure
cp .env.example .env

# Run CLI
./lakesh
# or
python lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

#### macOS

```bash
# Install Ollama
brew install ollama

# Pull models (qwen3-coder:30b recommended for coding, but any Ollama model works)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Navigate to project
cd /path/to/codeanalyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install ollama fastapi uvicorn rich chromadb python-dotenv

# Configure
cp .env .env

# Run CLI
./lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

#### Windows (PowerShell)

```powershell
# Install Ollama
# Download from https://ollama.com/download

# Pull models (qwen3-coder:30b recommended for coding, but any Ollama model works)
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text  # for semantic search

# Navigate to project
cd C:\path\to\codeanalyzer

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install ollama fastapi uvicorn rich chromadb python-dotenv

# Configure
copy .env .env

# Run CLI
python lakesh

# Run server
uvicorn lakesh_server:app --port 8765
```

## Configuration

Edit `.env` file to customize behavior:

```env
# Mode: "agent" (reads files, uses tools) or "chat" (model only, no tools)
LAKESH_MODE=agent

# Ollama model to use (any model supported by Ollama)
LAKESH_MODEL=qwen3-coder:30b

# Server port (for lakesh_server.py)
LAKESH_PORT=8765

# Maximum agent steps before timeout
LAKESH_MAX_STEPS=10
```

### Modes Explained

**Agent Mode** (`LAKESH_MODE=agent`):
- Uses intent classifier to decide when to use tools
- Reads files, searches code, runs commands
- Best for: debugging, code analysis, file operations
- Slower but more capable

**Chat Mode** (`LAKESH_MODE=chat`):
- Never uses tools, pure conversational AI
- Faster responses, no file access
- Best for: general questions, explanations, brainstorming
- Ideal when you don't need file operations

## Usage

### CLI (Interactive)

```bash
# Start interactive session
lakesh

# Single task
lakesh "fix the authentication bug"

# Specify model
lakesh --model llama3:8b "explain this code"
```

**CLI Commands:**
- `clear` - Reset conversation context
- `memory` - View saved memories
- `cd <path>` - Change directory
- `exit` - Quit

### HTTP Server

```bash
# Start server
uvicorn lakesh_server:app --port 8765

# Health check
curl http://localhost:8765/health

# Run task (sync)
curl -X POST http://localhost:8765/run \
  -H "Content-Type: application/json" \
  -d '{"task": "list files", "history": []}'

# Stream response
curl -X POST http://localhost:8765/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "explain main.py", "history": []}'
```

### OpenAI-Compatible API

The server provides an OpenAI-compatible endpoint for IDE integration:

```bash
# Chat completions
curl -X POST http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'

# List models
curl http://localhost:8765/v1/models

# List available tools (for Continue.dev function calling)
curl http://localhost:8765/v1/tools
```

**Continue.dev Configuration:**

See the detailed Continue.dev setup instructions in the "HTTP Server" section above for step-by-step configuration with VS Code.

Quick reference:
```json
{
  "apiBase": "http://localhost:8765/v1",
  "title": "Lakesh",
  "apiKey": "ollama"
}
```

## Codebase Indexing

For semantic search across your codebase:

```bash
# Index current directory
python indexer.py

# Index specific path
python indexer.py /path/to/project

# Index is saved to .chroma/ directory
```

## GPU Setup

To enable GPU acceleration:

```bash
# Run the GPU setup script
bash gpu_setup.sh

# Or manually configure Ollama
# Edit /etc/systemd/system/ollama.service.d/gpu.conf
# Add: Environment="OLLAMA_GPU_LAYERS=999"
```

## Tools Available

- **read_file(path)** - Read file contents
- **list_dir(path)** - List directory contents
- **write_file(path, content)** - Write to a file
- **run_command(cmd)** - Run shell command
- **search_code(query)** - Semantic code search
- **memory_get(key)** - Recall saved note
- **memory_set(key, value)** - Save a note

## Project Structure

```
codeanalyzer/
├── lakesh              # CLI script
├── lakesh_server.py    # HTTP server
├── indexer.py          # Codebase indexer
├── gpu_setup.sh        # GPU configuration
├── .env                # Configuration
├── .chroma/            # Vector database (auto-generated)
├── analyzer/           # Code analysis tools
│   ├── parser.py
│   └── extractor.py
└── requirements.txt    # Python dependencies
```

## Troubleshooting

**Model not found:**
```bash
# Check available models
ollama list

# Pull the model (any Ollama model works)
ollama pull qwen3-coder:30b
```

**GPU not being used:**
```bash
# Check NVIDIA driver
nvidia-smi

# Run GPU setup
bash gpu_setup.sh
```

**Import errors:**
```bash
# Install missing dependencies
pip install ollama fastapi uvicorn rich chromadb python-dotenv
```

**Port already in use:**
```bash
# Change port in .env
LAKESH_PORT=8766

# Or kill existing process
pkill -f uvicorn
```

## Suggestions for Improvement

### Performance
- **Model Quantization**: Use quantized models (e.g., `qwen2.5-coder:7b-q4`) for faster inference
- **Caching**: Implement response caching for repeated queries
- **Batch Processing**: Process multiple files in parallel during indexing
- **Streaming Optimization**: Improve streaming latency for large responses

### Features
- **Multi-file Context**: Allow reading multiple files in a single tool call
- **Git Integration**: Add git-specific tools (diff, blame, log)
- **Test Generation**: Automatically generate unit tests for code
- **Refactoring Suggestions**: Suggest code improvements and refactoring
- **Documentation**: Auto-generate docstrings and README files
- **Code Review**: Review PRs and suggest improvements

### UX
- **Web UI**: Add a web interface for non-terminal users
- **VS Code Extension**: Create a dedicated VS Code extension
- **Voice Input**: Add speech-to-text for hands-free coding
- **Project Templates**: Include project scaffolding tools
- **Hot Reload**: Auto-reload server on code changes

### Security
- **Sandboxing**: Run commands in a sandboxed environment
- **Path Restrictions**: Limit file access to specific directories
- **Audit Logging**: Log all file operations for security review
- **Rate Limiting**: Add rate limiting for API endpoints

### Architecture
- **Plugin System**: Allow custom tools via plugins
- **Model Switching**: Dynamic model switching based on task complexity
- **Distributed Processing**: Support for distributed codebase analysis
- **Database Options**: Support multiple vector databases (Pinecone, Weaviate)

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.
