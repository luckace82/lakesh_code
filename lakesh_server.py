"""
Lakesh Agent Server — optimised.
- Fast path for chat (no tools)
- Agent path only when needed
- GPU-accelerated via Ollama CUDA
Run: uvicorn lakesh_server:app --port 8765
"""

import json, os, subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import ollama

app = FastAPI(title="Lakesh")

MODEL      = os.environ.get("LAKESH_MODEL", "qwen3-coder:30b")
MODE       = os.environ.get("LAKESH_MODE", "agent")  # "agent" or "chat"
AGENT_NAME = os.environ.get("LAKESH_AGENT_NAME", "Lakesh")
MAX_STEPS  = int(os.environ.get("LAKESH_MAX_STEPS", "50"))

CHAT_SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a friendly local AI coding assistant.
Be concise and direct. For greetings, simple questions, or anything that does NOT need
file access — answer directly without using any tools."""

AGENT_SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a senior software engineer AI assistant with direct access to the filesystem.

CRITICAL RULES:
1. NEVER ask the user to paste or share file contents. You have read_file — use it.
2. If the user mentions a filename (e.g. server.py), ALWAYS call read_file on it immediately.
3. If you don't know the exact path, call list_dir first to find it, then read_file.
4. Only after reading the file should you analyse or respond about it.

When you need a tool, respond with EXACTLY this on one line:
TOOL_CALL: {{"name": "tool_name", "args": {{"arg1": "value1"}}}}

Available tools: read_file(path), list_dir(path), write_file(path, content),
run_command(cmd), search_code(query)

Give final answers in markdown."""


import re as _re

CHAT_ONLY = {"hi","hello","hey","thanks","thank you","ok","okay","sure","yes","no","bye","goodbye"}

AGENT_KEYWORDS = {
    "analyze","analyse","review","check","inspect","look at","open","read",
    "show","summarize","summarise","fix","edit","write","create","refactor",
    "debug","find","search","where","list","scan","run","execute","test",
    "file","folder","directory",".py",".js",".ts",".html",".json",".sh",
    "server","views","models","urls","settings","config","main","app",
    "error","bug","broken","failing","crash","function","class","import",
    "project","repo","codebase","database","migration","git","endpoint","api",
}

def needs_agent(task: str) -> bool:
    # If mode is "chat", never use tools
    if MODE == "chat":
        return False
    
    low = task.lower().strip()
    if low in CHAT_ONLY:
        return False
    if _re.search(r'\b\w+\.\w{1,5}\b', low):  # any filename pattern
        return True
    return any(k in low for k in AGENT_KEYWORDS)


def read_file(path):
    try:
        c = Path(path).read_text(errors="ignore")
        return c[:6000] + "\n[truncated]" if len(c) > 6000 else c
    except Exception as e:
        return f"Error: {e}"

def list_dir(path="."):
    try:
        return "\n".join(
            f"{e.name}{'/' if e.is_dir() else ''}"
            for e in sorted(Path(path).iterdir())
        )
    except Exception as e:
        return f"Error: {e}"

def write_file(path, content):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error: {e}"

def run_command(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return out[:2000] if out else "(no output)"
    except Exception as e:
        return f"Error: {e}"

def search_code(query):
    try:
        import chromadb
        client = chromadb.PersistentClient(path=".chroma")
        col = client.get_collection("codebase")
        emb = ollama.embeddings(model="nomic-embed-text", prompt=query)["embedding"]
        results = col.query(query_embeddings=[emb], n_results=4)
        return "\n\n---\n".join(
            f"{f}:\n{d[:400]}"
            for f, d in zip(results["ids"][0], results["documents"][0])
        )
    except Exception as e:
        return f"Search unavailable: {e}"

TOOLS = {
    "read_file": read_file, "list_dir": list_dir,
    "write_file": write_file, "run_command": run_command,
    "search_code": search_code
}


def parse_tool_call(text):
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("TOOL_CALL:"):
            try:
                return json.loads(line[len("TOOL_CALL:"):].strip())
            except:
                pass
    return None

def run_chat_sync(task, history):
    """Fast path — direct model call, no tool loop."""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages += (history or [])[-10:]
    messages.append({"role": "user", "content": task})
    resp = ollama.chat(model=MODEL, messages=messages, stream=False)
    return resp["message"]["content"]

def run_agent_sync(task, history):
    """Full agent loop — only when tools are needed."""
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages += (history or [])[-10:]
    messages.append({"role": "user", "content": task})
    for _ in range(MAX_STEPS):
        resp = ollama.chat(model=MODEL, messages=messages, stream=False)
        reply = resp["message"]["content"]
        messages.append({"role": "assistant", "content": reply})
        tc = parse_tool_call(reply)
        if not tc:
            return reply
        name, args = tc.get("name",""), tc.get("args",{})
        result = TOOLS[name](**args) if name in TOOLS else f"Unknown tool: {name}"
        messages.append({"role": "user", "content": f"Tool result:\n{result}"})
    return "Reached max steps."

def run_chat_stream(task, history):
    """Fast streaming path — no tools."""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages += (history or [])[-10:]
    messages.append({"role": "user", "content": task})
    for chunk in ollama.chat(model=MODEL, messages=messages, stream=True):
        yield chunk["message"]["content"]

def run_agent_stream(task, history):
    """Agent streaming path — tools shown inline."""
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages += (history or [])[-10:]
    messages.append({"role": "user", "content": task})
    for _ in range(MAX_STEPS):
        full = ""
        for chunk in ollama.chat(model=MODEL, messages=messages, stream=True):
            token = chunk["message"]["content"]
            full += token
            if "TOOL_CALL:" not in full:
                yield token
            if "TOOL_CALL:" in full and full.rstrip().endswith("}"):
                break
        messages.append({"role": "assistant", "content": full})
        tc = parse_tool_call(full)
        if not tc:
            return
        name, args = tc.get("name",""), tc.get("args",{})
        yield f"\n\n> Using `{name}`...\n\n"
        result = TOOLS[name](**args) if name in TOOLS else f"Unknown tool: {name}"
        messages.append({"role": "user", "content": f"Tool result:\n{result}"})


class TaskRequest(BaseModel):
    task: str
    history: list = []


@app.get("/health")
def health():
    try:
        ollama.list()
        return {"status": "ok", "model": MODEL}
    except Exception as e:
        return JSONResponse(503, {"status": "error", "detail": str(e)})

@app.post("/run")
def run(req: TaskRequest):
    if needs_agent(req.task):
        return {"result": run_agent_sync(req.task, req.history)}
    return {"result": run_chat_sync(req.task, req.history)}

@app.post("/stream")
def stream(req: TaskRequest):
    gen = run_agent_stream if needs_agent(req.task) else run_chat_stream
    return StreamingResponse(gen(req.task, req.history), media_type="text/plain")

@app.post("/v1/chat/completions")
async def openai_compat(request: Request):
    import time
    body = await request.json()
    messages = body.get("messages", [])
    stream_mode = body.get("stream", False)
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    task = user_msgs[-1] if user_msgs else ""
    history = [m for m in messages[:-1] if m.get("role") in ("user","assistant")]

    use_agent = needs_agent(task)

    if stream_mode:
        gen = run_agent_stream if use_agent else run_chat_stream
        def openai_stream():
            cid = f"cmpl-{int(time.time())}"
            for token in gen(task, history):
                chunk = {"id": cid, "object": "chat.completion.chunk",
                         "choices": [{"delta": {"content": token}, "index": 0, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            done = {"id": cid, "object": "chat.completion.chunk",
                    "choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n"
        return StreamingResponse(openai_stream(), media_type="text/event-stream")
    else:
        fn = run_agent_sync if use_agent else run_chat_sync
        result = fn(task, history)
        return {"id": "cmpl-lakesh", "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": result},
                             "index": 0, "finish_reason": "stop"}]}

@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "lakesh"}]}

@app.get("/v1/tools")
def list_tools():
    """Expose available tools in OpenAI function calling format for Continue.dev"""
    return {
        "object": "list",
        "data": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file from disk",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Absolute or relative path to the file"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List files and directories in a given path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path (default: current directory)"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file (creates parent directories if needed)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path to write to"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write to the file"
                            }
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Execute a shell command in the project directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cmd": {
                                "type": "string",
                                "description": "Shell command to execute"
                            }
                        },
                        "required": ["cmd"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Semantic search across the indexed codebase",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for semantic code search"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
