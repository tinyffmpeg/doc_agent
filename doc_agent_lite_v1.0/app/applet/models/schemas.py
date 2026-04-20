from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel

class Document(BaseModel):
    url: str
    title: str
    content: str       # 原始爬取的完整文本
    score: int = 0     # AI 评分 (0-100)
    summary: str = ""  # AI 生成的入选/淘汰理由
    is_valid: bool = False
    raw_file_bytes: bytes | None = None  # 原始二进制文献（如PDF或HTML代码）
    file_extension: str = ".md"          # 文件后缀，比如 .pdf, .html

class AgentState(TypedDict):
    task_id: str             # 唯一任务ID (时间戳生成)
    topic: str               # 用户输入的中文课题
    queries: List[str]       # Plan 节点拆解出的检索词
    raw_documents: List[Document]   # Search 节点抓取的所有原始文档
    valid_documents: List[Document] # Evaluate 节点过滤后的高质量文档
    logs: List[str]          # 供 UI SSE 推送的流式执行日志
    status: str              # 当前状态: planning, searching, evaluating, archiving, completed, failed

