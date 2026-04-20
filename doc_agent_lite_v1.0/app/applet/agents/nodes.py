import yaml
import asyncio
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from models.schemas import AgentState, Document
from utils.json_parser import parse_qwen_json
from utils.logger import task_logger
from tools.web_scraper import concurrent_search_and_fetch
from tools.vector_store import vectorize_and_store
import os
import zipfile

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# 本地 Ollama 客户端
llm = ChatOpenAI(
    base_url=config["llm"]["base_url"],
    model=config["llm"]["model"],
    api_key="ollama", # placeholder needed for langchain's openai client
    temperature=config["llm"]["temperature"]
)

ollama_semaphore = asyncio.Semaphore(2)

def plan(state: AgentState) -> Dict:
    task_id = state["task_id"]
    topic = state["topic"]
    task_logger.add_log(task_id, f"[Plan] 开始拆解课题意图: {topic}")
    
    prompt = f"""你是一个专业的学术情报检索专家。根据用户的课题，提炼并生成 3 个用于检索国际顶级学术数据库（如 OpenAlex, Nature, arXiv）的【纯英文】关键词或短语组合。你必须且只能输出严格的 JSON 数组格式，不要包含 ```json 等 markdown 标记。
课题：{topic}
示例输出：["Single photon detector efficiency", "Lightweight photodetector space application", "SNSPD review"]"""

    response = llm.invoke([HumanMessage(content=prompt)])

    parsed_queries = parse_qwen_json(response.content)
    
    queries = parsed_queries if isinstance(parsed_queries, list) else [topic]
    task_logger.add_log(task_id, f"[Plan] 拆解得到查询词: {queries}")
    
    return {"queries": queries, "status": "searching"}

async def search(state: AgentState) -> Dict:
    task_id = state["task_id"]
    queries = state["queries"]
    task_logger.add_log(task_id, "[Search] 并发抓取文档中...")
    
    docs = await concurrent_search_and_fetch(queries, config["scraper"]["max_urls_per_query"], task_id)
    task_logger.add_log(task_id, f"[Search] 成功返回 {len(docs)} 篇原始文档内容")
    
    return {"raw_documents": docs, "status": "evaluating"}

async def evaluate_single_doc(doc: Document, topic: str) -> Document:
    text = doc.content
    truncated_content = text if len(text) < 4000 else text[:3000] + "\n...[中间部分省略]...\n" + text[-1000:]
    
    prompt = f"""请评估此文档片段是否与课题【{topic}】高度相关。请严格输出 JSON，格式如: {{"is_relevant": true, "score": 85, "reason": "一句话理由"}}
文档内容：
{truncated_content}"""

    async with ollama_semaphore:
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            result = parse_qwen_json(response.content)
            
            if isinstance(result, dict):
                doc.score = int(result.get("score", 0))
                doc.summary = str(result.get("reason", ""))
                doc.is_valid = bool(result.get("is_relevant", False))
        except Exception as e:
            print(f"Eval error: {e}")
            
    return doc

async def evaluate(state: AgentState) -> Dict:
    task_id = state["task_id"]
    topic = state["topic"]
    raw_docs = state["raw_documents"]
    task_logger.add_log(task_id, f"[Evaluate] 开始评估 {len(raw_docs)} 篇文档的质量（使用并发锁保护）...")
    
    tasks = [evaluate_single_doc(doc, topic) for doc in raw_docs]
    evaluated_docs = await asyncio.gather(*tasks)
    
    valid_docs = [doc for doc in evaluated_docs if doc.score >= 80 and doc.is_valid]
    task_logger.add_log(task_id, f"[Evaluate] 筛选通过 {len(valid_docs)} 篇高质量文档")
    
    return {"valid_documents": valid_docs, "status": "archiving"}

def archive(state: AgentState) -> Dict:
    task_id = state["task_id"]
    valid_docs = state["valid_documents"]
    task_logger.add_log(task_id, "[Archive] 正在将其持久化与向量化...")
    
    if not valid_docs:
        task_logger.add_log(task_id, "[Archive] 无有效文档，跳过归档。")
        return {"status": "completed"}
        
    base_dir = f"storage/archives/{task_id}"
    raw_dir = f"{base_dir}/raw"
    os.makedirs(raw_dir, exist_ok=True)
    
    # 本地文件写入
    for i, doc in enumerate(valid_docs):
        safe_title = "".join(c for c in doc.title if c.isalnum() or c in " _-")[:50]
        
        # 1. 写入带有 AI 信息和纯净文本的 .md 版
        md_file_path = f"{raw_dir}/{i+1}_{safe_title}.md"
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(f"# {doc.title}\nURL: {doc.url}\nScore: {doc.score}\nReason: {doc.summary}\n\n{doc.content}")

        # 2. 如果存在原始二进制文件（如提取到的 PDF），一并写入磁盘
        if doc.raw_file_bytes:
            raw_ext = doc.file_extension if doc.file_extension else ""
            raw_file_path = f"{raw_dir}/{i+1}_{safe_title}_Original{raw_ext}"
            with open(raw_file_path, "wb") as f_raw:
                f_raw.write(doc.raw_file_bytes)

    # ChromaDB 向量化
    vectorize_and_store(task_id, valid_docs, config["llm"]["base_url"], config["llm"]["embedding_model"])
    
    # 生成 zip
    zip_path = f"{base_dir}/archive.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file != "archive.zip":
                    zipf.write(os.path.join(root, file), 
                             os.path.relpath(os.path.join(root, file), base_dir))
                             
    task_logger.add_log(task_id, "[Archive] 归档完成。")
    return {"status": "completed"}
