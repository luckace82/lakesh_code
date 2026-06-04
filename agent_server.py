from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import agent_loop
import ollama

app = FastAPI()

class Task(BaseModel):
    task: str

@app.post('/run')
def run(t: Task):
    return {'result': agent_loop(t.task)}

@app.post('/stream')
def stream(t: Task):
    def gen():
        for chunk in ollama.chat(
            model='qwen3-coder:30b',
            messages=[{'role':'user','content':t.task}],
            stream=True
        ):
            yield chunk['message']['content']
    return StreamingResponse(gen(), media_type='text/plain')
