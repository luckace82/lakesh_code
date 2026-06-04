import os, subprocess

def read_file(path):
    return open(path).read()

def list_dir(path):
    return '\n'.join(os.listdir(path))

def write_file(path, content):
    open(path, 'w').write(content)
    return f'Written: {path}'

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr

TOOLS = {
    'read_file': read_file,
    'list_dir': list_dir,
    'write_file': write_file,
    'run_command': run_command,
}
