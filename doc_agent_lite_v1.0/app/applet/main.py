import time
import asyncio
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from agents.graph import create_mining_graph
from utils.logger import task_logger
import os

app = FastAPI(title="DocAgent Lite API")

class TaskRequest(BaseModel):
    topic: str

tasks_store = {}

async def run_langgraph(task_id: str, topic: str):
    graph = create_mining_graph()
    initial_state = {
        "task_id": task_id,
        "topic": topic,
        "queries": [],
        "raw_documents": [],
        "valid_documents": [],
        "logs": [],
        "status": "planning"
    }
    
    try:
        task_logger.add_log(task_id, "开始执行流处理...")
        final_state = await graph.ainvoke(initial_state)
        tasks_store[task_id] = final_state
        task_logger.add_log(task_id, "[DONE] 任务执行完毕")
    except Exception as e:
        task_logger.add_log(task_id, f"[ERROR] 任务失败: {str(e)}")
        initial_state["status"] = "failed"
        tasks_store[task_id] = initial_state

@app.post("/api/task/start")
async def start_task(req: TaskRequest, background_tasks: BackgroundTasks):
    task_id = str(int(time.time()))
    background_tasks.add_task(run_langgraph, task_id, req.topic)
    return {"task_id": task_id}

@app.get("/api/task/{task_id}/stream")
async def stream_logs(task_id: str):
    async def log_generator():
        last_idx = 0
        while True:
            logs = task_logger.get_logs(task_id, last_idx)
            for log in logs:
                yield f"data: {log}\n\n"
            last_idx += len(logs)
            
            if "[DONE]" in "".join(logs) or "[ERROR]" in "".join(logs):
                break
            await asyncio.sleep(0.5)
            
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/task/{task_id}/result")
async def get_result(task_id: str):
    state = tasks_store.get(task_id, {})
    # FastAPI can't serialize raw bytes (raw_file_bytes) inside the Document models.
    # We strip out the raw_file_bytes from the response to prevent UnicodeDecodeError.
    
    clean_state = {}
    for key, value in state.items():
        if key in ["raw_documents", "valid_documents"]:
            clean_docs = []
            for doc in value:
                # If doc is a Pydantic model, convert to dict. If it's a dict, copy it.
                doc_dict = doc.model_dump() if hasattr(doc, "model_dump") else dict(doc)
                if "raw_file_bytes" in doc_dict:
                    doc_dict["raw_file_bytes"] = None # Remove binary data
                clean_docs.append(doc_dict)
            clean_state[key] = clean_docs
        else:
            clean_state[key] = value
            
    return clean_state

@app.get("/api/download/{task_id}")
async def download_archive(task_id: str):
    file_path = f"storage/archives/{task_id}/archive.zip"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/zip", filename=f"archive_{task_id}.zip")
    return {"error": "Archive not found"}
