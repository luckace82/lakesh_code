import ollama, json, argparse
from tools import TOOLS

def parse_tool_call(reply):
    import re
    match = re.search(r'TOOL_CALL:\s*(\w+)\((.*?)\)', reply, re.DOTALL)
    if match:
        tool_name = match.group(1)
        args_str = match.group(2).strip()
        try:
            args = json.loads(args_str) if args_str else {}
            if isinstance(args, str):
                if tool_name == 'list_dir':
                    args = {'path': args}
                elif tool_name == 'read_file':
                    args = {'path': args}
                elif tool_name == 'write_file':
                    args = {'path': args}
                elif tool_name == 'run_command':
                    args = {'cmd': args}
        except:
            args = {}
            if args_str:
                args_str = args_str.strip('"\'')
                if not '=' in args_str and not '{' in args_str:
                    if tool_name == 'list_dir':
                        args['path'] = args_str
                    elif tool_name == 'read_file':
                        args['path'] = args_str
                    elif tool_name == 'write_file':
                        args['path'] = args_str
                    elif tool_name == 'run_command':
                        args['cmd'] = args_str
                else:
                    for pair in args_str.split(','):
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            args[key.strip()] = value.strip().strip('"\'')
        return {'name': tool_name, 'args': args}
    return None

def agent_loop(task, max_steps=10):
    system_prompt = """You are a senior engineer working on a Django + React codebase.
- Django backend in /backend, React frontend in /frontend
- Use Python type hints, follow PEP 8
- For React: functional components, hooks only, no class components
- When editing files, show unified diff format
- Always explain what you changed and why
- If you need to read a file first, use read_file() before answering

You are an AI agent with access to tools. When you need to use a tool, format your response as:
TOOL_CALL: tool_name({"arg": "value"})

Available tools:
- read_file(path): Read the contents of a file
- list_dir(path): List files in a directory
- write_file(path, content): Write content to a file
- run_command(cmd): Run a shell command

Use tools when you need to interact with the file system or run commands. Be specific with paths. Always use valid JSON format for arguments."""
    history = [
        {'role':'system','content':system_prompt},
        {'role':'user','content':task}
    ]
    for _ in range(max_steps):
        resp = ollama.chat(
            model='qwen3-coder:30b',
            messages=history
        )
        reply = resp['message']['content']
        history.append({'role':'assistant','content':reply})
        tool_call = parse_tool_call(reply)
        if not tool_call:
            return reply
        result = TOOLS[tool_call['name']](**tool_call['args'])
        history.append({'role':'user','content':f'Tool result: {result}'})
    return 'Max steps reached'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True, help='Task for the agent')
    args = parser.parse_args()
    result = agent_loop(args.task)
    print(result)
