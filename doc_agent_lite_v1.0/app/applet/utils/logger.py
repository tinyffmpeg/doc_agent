import os
import time
from typing import Dict, List

class TaskLogger:
    def __init__(self):
        self.task_logs: Dict[str, List[str]] = {}

    def add_log(self, task_id: str, message: str):
        if task_id not in self.task_logs:
            self.task_logs[task_id] = []
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        self.task_logs[task_id].append(log_msg)
        print(f"[Task {task_id}] {log_msg}")

    def get_logs(self, task_id: str, since_idx: int = 0) -> List[str]:
        if task_id not in self.task_logs:
            return []
        return self.task_logs[task_id][since_idx:]

task_logger = TaskLogger()
