这份文档基于去掉了“Report Writer”节点的精简策略进行了全面重构。系统定位从“自动写稿机器人”转变为**“高精度的智能文献与情报挖掘流水线（Data Mining Pipeline）”**。

这套方案**完全抛弃了对 GPT-4o 等超大参数模型的依赖**，在保证极高工程稳定性的同时，可轻松实现本地化部署或极低成本的 API 运行。

请将以下内容保存为 `DocAgentLiteV1.0.md`：

--- START OF FILE DocAgentLiteV1.0.md ---

# DocAgent Lite V1.0：智能文献挖掘与情报收集架构

> **版本定位**：面向高精度数据挖掘的轻量级（Lite）生产环境工作流。剔除长文生成环节，聚焦**“意图拆解 → 深度检索 → AI苛刻过滤 → 结构化资料交付”**。
> **核心优势**：无需 GPT-4o 等千亿参数模型，仅依赖 7B~14B 开源小模型即可完美运转；硬件门槛极低，支持纯本地化私有部署；UI 交互即刻反馈。

### 一、 工作流定义（Pipeline Nodes）

去除了复杂的报告撰写节点后，整个工作流更加线性和可控，单次任务成功率和执行速度大幅提升。

| 节点 (Node) | 职责定义 | 输入 | 输出 | 关键能力与模型要求 |
| :--- | :--- | :--- | :--- | :--- |
| **1. Plan** | 意图理解与多维度拆解 | 用户泛指令 (如中文短句) | 5-8 个多语言检索 Query (JSON) | • 短上下文，强指令遵循<br>• 要求模型具备准确输出 JSON 的能力 |
| **2. Search** | 并行检索与降级抓取 | Query 列表 | 原始网页/PDF 文本数据 | • 无需大模型<br>• 依靠并发控制、反爬绕过与工具降级策略 |
| **3. Evaluate** | 内容清洗与苛刻打分 | 单篇原始文本数据 | 评分(0-100) + 核心入选理由 | • 中长上下文 (约 32k)<br>• **一次只读一篇**，进行二分类/打分与一句话信息抽取 |
| **4. Archive** | 磁盘持久化与向量化 | 达标的数据列表 (≥80分) | 本地档案路径 + 向量 ID | • 无需大模型<br>• 保证文件 IO 的幂等性，生成结构化本地目录 |

### 二、 核心系统架构图（含交互层）

```mermaid
graph TD
    subgraph UI 交互层 (Streamlit App)
        U1[用户输入课题指令] --> U2[实时执行流展示 SSE]
        U2 --> U3[🎯 交付：高价值情报库展示 & 资料打包下载]
    end

    U1 -->|1. Submit HTTP| B[API Gateway <br> FastAPI + SSE + 静态服务]
    B -->|2. Stream Logs| U2
    B -->|3. Data Ready| U3
    
    B --> C[LangGraph Orchestrator <br> State + Checkpoint]
    
    subgraph Doc Mining Agent
        C --> D[Plan Node <br> 动态拆 Query]
        D --> E[Search Node <br> 并行抓取 + 降级处理]
        E --> F[Evaluate Node <br> 逐篇清洗 + AI 打分]
        
        %% 负向反馈闭环：如果全部被筛掉，要求重新规划
        F -- "有效文档为 0" --> D
        
        F -- "质量达标" --> G[Archive Node <br> IO 写入 + ChromaDB]
    end
    
    G --> M[任务完成标志位更新]

    subgraph 本地持久化 (100% 数据归属)
        N[📂 storage/archives/ <br> 原始PDF与Markdown]
        O[🧠 ChromaDB <br> 供后续检索扩展]
        G -.-> N
        G -.-> O
    end
```

### 三、 UI 交互与交付界面 (Streamlit Design)

由于移除了大纲审核和长文写稿环节，UI 的重点转变为**“过程透明”**与**“数据资产呈现”**。

#### 1. 任务提交与过程透明 (Progress Dashboard)
*   **输入框**：用户输入“`轻小型智能单光子探测器件`”，点击提交。
*   **沉浸式过程日志**：UI 接收后端的 SSE 实时流，以动态气泡或控制台的形式展示 AI 的“心路历程”：
    *   *🤖 意图拆解：生成关键词 [“SPAD compact”, “轻小型单光子 综述”, “单光子探测 阵列化”]...*
    *   *🌐 抓取中：正在下载 arXiv:2305.xxxx.pdf... (成功)*
    *   *🔍 AI 评估：文章 [网页标题] 仅为产品广告，评分 30，已丢弃 🗑️*
    *   *✨ AI 评估：文章 [论文标题] 包含阵列化核心数据，评分 92，已入库 💾*

#### 2. 成果交付区 (Deliverables Tabs)
任务完成后，展示三个并排的 Tabs，直接交付价值：

*   **Tab 1: 💡 核心情报库 (High-Value Intel)**
    *   以**卡片流 (Card View)** 或 **数据表 (DataFrame)** 形式展示最终过关的文献。
    *   **展示字段**：`来源标识 (PDF/Web)` | `标题与链接` | `AI 评分` | `🧠 AI 一句话入选理由 (Summary)`。
    *   *体验优势：用户不需要看长篇大论，直接看 AI 给出的入选理由，快速判断哪篇文献最值得深读。*
*   **Tab 2: 📦 本地知识包 (Local Archives)**
    *   提供文件树浏览器（Tree View）查看 `storage/archives/{task_id}/` 目录。
    *   提供 **`📥 一键打包下载 (.zip)`** 功能，将清洗好的干净 Markdown 正文和原始 PDF 统统下载到本地。
*   **Tab 3: ⚙️ 极客日志 (Metrics)**
    *   耗时统计、抓取成功率、过滤率（如：抓了 50 篇，淘汰 42 篇，保留 8 篇）以及 Token 消耗。

### 四、 轻量化大模型选型策略 (Model Requirements)

本架构彻底移除了长上下文拼装撰写的需求，因此**不推荐使用 GPT-4o/Claude-3.5 等高价模型**。

#### 方案 A：纯本地私有部署（推荐涉密/军工/高校场景）
*   **硬件要求**：单台 PC（搭载 1 张 RTX 3090/4090 24GB 显卡）或 Mac M2/M3 Max。
*   **推理模型**：部署 **`Qwen2.5-7B-Instruct`** 或 **`GLM-4-9B-Chat`** (通过 vLLM 或 Ollama)。
    *   *Plan 节点*：7B 模型配合 LangChain `with_structured_output`，足以稳定输出拆解的 JSON Query。
    *   *Evaluate 节点*：利用模型的 32k 上下文，逐篇阅读（每篇独立判断，无记忆混淆），给出评分和理由。
*   **向量模型**：`bge-m3` (支持长文本与多语言，占用显存极小)。

#### 方案 B：极致性价比 API（推荐无 GPU 的团队）
*   **核心模型**：调用 **`DeepSeek-V3`** 或 阿里云 **`Qwen-Plus`** API。
*   **成本核算**：单次任务（拆解意图 + 并发抓取 30 篇长文 + 逐篇阅读并打分抽取）处理的总 Tokens 约在 20万~40万之间。按当前国产 API 计费标准，**单次任务综合成本低于 0.5 元人民币**。

### 五、 核心代码修改范例 (Evaluate 节点精简)

模型不再需要兼顾写稿，只需要冷酷地扮演“裁判员”。

```python
# agents/research_orchestrator.py
from pydantic import BaseModel, Field

class DocEvaluation(BaseModel):
    is_relevant: bool = Field(description="文章是否与课题高度相关")
    score: int = Field(description="文章质量与相关度打分 (0-100)")
    reason: str = Field(description="如果相关，请用50字以内概括其核心贡献或数据；如果不相关，说明原因。")

def evaluate_node(state: AgentState):
    # 使用轻量级模型 (如 Qwen2.5-7B)
    llm = get_lite_llm().with_structured_output(DocEvaluation)
    
    valid_docs = []
    for doc in state.raw_documents:
        # 逐篇让 AI 审核
        prompt = f"课题：{state.topic}\n待审文档内容片段：\n{doc.content[:15000]}...\n请评估其价值。"
        eval_result = llm.invoke(prompt)
        
        if eval_result.is_relevant and eval_result.score >= 80:
            doc.score = eval_result.score
            doc.summary = eval_result.reason
            valid_docs.append(doc)
            
    # 如果全军覆没，返回 Plan 节点要求换词重搜
    if not valid_docs:
        return {"status": "failed_need_replan"}
        
    return {"valid_documents": valid_docs, "status": "ready_to_archive"}
```

### 六、 项目目录结构（Lite 版）

```text
doc_agent_lite_v1.0/
├── pyproject.toml
├── main.py                          # FastAPI后端: 提供提交、SSE流、Zip打包下载
├── config.yaml                      # 爬虫并发限制, 本地模型路径/API Key
├── agents/
│   ├── orchestrator.py              # LangGraph 顶层图 (无 Writer，流转更简单)
│   └── doc_mining_agent.py          # 包含 Plan / Search / Evaluate 节点
├── tools/
│   ├── search_tools.py
│   ├── scraper_tools.py             # 动态抓取与异常降级策略
│   └── archive_tools.py             # 纯 IO: 写入 Markdown, 生成 Metadata.json, 压缩 Zip
├── storage/
│   ├── archives/                    # 存储库
│   └── chroma_db/                   # 供未来扩展 RAG 使用
├── ui/
│   └── streamlit_app.py             # 交互端: 包含实时日志、情报卡片展示、下载按钮
└── utils/
    ├── rate_limiter.py              # 域名级反爬限流器 (防 arXiv 封禁)
    └── json_parser.py               # 确保本地小模型输出 JSON 的容错补救脚本
```

### 七、 实施路径建议

1. **第一阶段 (CLI MVP)**：先跑通本地 7B 模型的 API 调用。使用硬编码课题测试 `Plan -> Search -> Evaluate` 的准确率，重点调试模型在 `Evaluate` 节点输出 JSON（打分+理由）的稳定性。
2. **第二阶段 (Scraper 强化)**：接入 `Playwright/JinaReader` 降级策略，并在 `Search` 节点中实现并发控制，确保爬虫不会因 429 报错崩溃。
3. **第三阶段 (UI & API)**：包裹 FastAPI，利用 Server-Sent Events (SSE) 将终端日志推送到 Streamlit，并实现 `storage/` 目录内容的 Zip 动态打包下载。

--- END OF FILE DocAgentLiteV1.0.md ---




############################################################################################
DocAgent Lite V1.1
#
###########################################################################################



这份文档是为你量身定制的 “Code-Ready（可直接用于生成代码）” 的架构设计书。你可以直接将这份文档发给 Cursor、Claude 3.5 Sonnet 或 ChatGPT，并附上指令：“请严格按照这份架构文档，为我从零开始编写整个项目的代码”。

它包含了清晰的模块划分、状态定义、接口规范以及专门为 qwen2.5:7b 优化的关键算法逻辑。

--- START OF FILE DocAgentLite_Local_V1.1_CodeReady.md ---

DocAgent Lite V1.1 纯本地文献挖掘系统：开发与编码规范

系统愿景：构建一个完全运行在本地（无外部大模型API依赖）、基于 qwen2.5:7b 的智能文献检索与挖掘清洗流水线。
技术栈：Python 3.11+, FastAPI (后端), Streamlit (前端 UI), LangGraph (工作流调度), LangChain (模型接口), ChromaDB (本地向量库), Ollama (本地大模型基座)。

一、 系统核心状态定义 (Agent State)

LangGraph 的状态流转是整个系统的核心。必须在 models/schemas.py 中严格定义。

code
Python
download
content_copy
expand_less
from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel

class Document(BaseModel):
    url: str
    title: str
    content: str       # 原始爬取的完整文本
    score: int = 0     # AI 评分 (0-100)
    summary: str = ""  # AI 生成的入选/淘汰理由
    is_valid: bool = False

class AgentState(TypedDict):
    task_id: str             # 唯一任务ID (时间戳生成)
    topic: str               # 用户输入的中文课题
    queries: List[str]       # Plan 节点拆解出的检索词
    raw_documents: List[Document]   # Search 节点抓取的所有原始文档
    valid_documents: List[Document] # Evaluate 节点过滤后的高质量文档
    logs: List[str]          # 供 UI SSE 推送的流式执行日志
    status: str              # 当前状态: planning, searching, evaluating, archiving, completed, failed
二、 核心工作流节点实现规范 (LangGraph Nodes)

位于 agents/doc_mining_agent.py，必须严格按照以下逻辑编写。

1. Plan 节点 (意图拆解)

模型调用：使用连接到本地 Ollama 的 ChatOpenAI 客户端。

base_url="http://localhost:11434/v1", model="qwen2.5:7b", temperature=0.1

Prompt 约束：必须在 Prompt 中提供 Few-Shot 示例，严禁模型输出多余废话。

“你是一个专业的情报检索专家。根据用户的课题，生成 3 个高质量的搜索引擎查询词（需包含中英文专业术语）。你必须且只能输出严格的 JSON 数组格式，不要包含 ```json 等 markdown 标记。”

解析兜底：调用 utils.json_parser.parse_qwen_json() 强制提取 JSON 列表赋值给 state["queries"]。

2. Search 节点 (并发检索与抓取)

并发检索：对 state["queries"] 使用 Tavily 或 DuckDuckGo 并发搜索，收集去重后的 URL 列表（最多 15 个）。

降级抓取：

遍历 URL，优先调用 JinaReaderScraper (利用其 API 返回干净 Markdown)。

遇到 PDF 链接，使用 pdfplumber 或本地解析库提取文本。

将结果封装为 Document 对象存入 state["raw_documents"]。

3. Evaluate 节点 (核心防爆显存设计，极其重要)

这是本地 7B 模型的瓶颈区，必须包含以下三项工程保护：

保护一：并发锁。必须使用 asyncio.Semaphore(2) 限制同时向 Ollama 发起的请求不超过 2 个，防止 GPU OOM。

保护二：首尾截断法。绝不可将全文发给模型。

code
Python
download
content_copy
expand_less
# 截断逻辑示例
text = doc.content
truncated_content = text if len(text) < 4000 else text[:3000] + "\n...[中间部分省略]...\n" + text[-1000:]

保护三：单篇打分 Prompt。

“请评估此文档片段是否与课题【{topic}】高度相关。请严格输出 JSON：{{"is_relevant": true/false, "score": 85, "reason": "一句话理由"}}”

逻辑：遍历 raw_documents，只有 score >= 80 的存入 state["valid_documents"]。

4. Archive 节点 (持久化)

本地文件写入：在 storage/archives/{task_id}/ 下创建 raw/ 目录，将 valid_documents 的标题和内容写入 .md 文件。

ChromaDB 向量化：

初始化：OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")

将打分合格的文档切块后存入本地 ChromaDB 目录。

生成压缩包：将 storage/archives/{task_id}/ 打包为 archive.zip。

三、 API 与 UI 交互规范

系统必须采用前后端分离架构，防止长时间执行导致请求超时。

1. FastAPI 后端 (main.py)

需要实现三个核心路由：

POST /api/task/start: 接收 {topic: str}，生成并返回 task_id，后台异步启动 LangGraph 图执行。

GET /api/task/{task_id}/stream: Server-Sent Events (SSE) 接口。读取数据库或内存队列中的执行日志，源源不断地推送到前端。

GET /api/download/{task_id}: 提供 archive.zip 的静态文件下载服务。

2. Streamlit 前端 (ui/streamlit_app.py)

区域 A (输入区)：顶部输入框，输入课题，点击“开始挖掘”。

区域 B (状态监听区)：使用 st.status 或动态日志框，连接后端的 SSE 接口，实时打印（如：[Search] 正在抓取..., [Evaluate] 发现高价值文档...）。

区域 C (成果交付区 - Tabs)：
当收到任务完成信号后，展示双页签：

Tab 1 (情报库)：使用 st.dataframe 展示过滤后的高分文档。列名：文档标题 | AI评分 | 核心亮点(Summary) | 来源链接。

Tab 2 (资料下载)：提供大号按钮 📥 下载完整归档资料包 (.zip)，点击触发 FastAPI 的下载路由。

四、 必备工具类与容错组件 (Utils)

必须在 utils/ 目录下实现以下基建代码。

utils/json_parser.py (暴力 JSON 提取器)

必须实现针对 qwen2.5:7b 的正则提取算法，以防 Python json.loads 报错。

code
Python
download
content_copy
expand_less
import re
import json
import logging

def parse_qwen_json(text: str) -> dict:
    """强制从大模型输出的混乱文本中提取 JSON"""
    # 1. 尝试匹配 ```json ... ``` 块
    match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        target_str = match.group(1)
    else:
        target_str = text
        
    # 2. 如果没有 markdown 标记，暴力寻找第一个 { 或 [ 
    start_obj = target_str.find('{')
    start_arr = target_str.find('[')
    
    if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
        end = target_str.rfind('}')
        if end != -1: target_str = target_str[start_obj:end+1]
    elif start_arr != -1:
        end = target_str.rfind(']')
        if end != -1: target_str = target_str[start_arr:end+1]
        
    try:
        return json.loads(target_str)
    except json.JSONDecodeError as e:
        logging.error(f"JSON Parsing failed. Raw text: {text}")
        # 返回默认兜底结构防止流水线崩溃
        return {"error": True, "parsed": False}
五、 项目目录结构要求

请 AI 编码助手严格按照以下树状结构生成所有文件：

code
Text
download
content_copy
expand_less
doc_agent_local_v1.1/
├── requirements.txt
├── config.yaml                 # 存放 Ollama url, 抓取并发数等
├── main.py                     # FastAPI 启动入口 (包含 SSE 逻辑)
├── agents/
│   ├── __init__.py
│   ├── graph.py                # LangGraph 流程连线定义
│   └── nodes.py                # Plan, Search, Evaluate, Archive 具体逻辑
├── models/
│   ├── __init__.py
│   └── schemas.py              # AgentState, Document 模型定义
├── tools/
│   ├── __init__.py
│   ├── web_scraper.py          # 网页/PDF抓取逻辑
│   └── vector_store.py         # ChromaDB + OllamaEmbeddings 封装
├── ui/
│   └── streamlit_app.py        # Streamlit 界面
└── utils/
    ├── __init__.py
    ├── json_parser.py          # 容错 JSON 解析
    └── logger.py               # 统一定义日志和 SSE 队列写入器

致 AI 编程助手：
请深刻理解这是一个基于本地 7B 模型的高并发数据处理流。请在实现代码时，严格落实我提出的并发锁 (Semaphore)、长文本截断和正则 JSON 提取这三项工程保护机制，确保系统在 24GB 显存的机器上不会崩溃。请从基础模型 (schemas) 和配置开始，逐步为我生成完整的可执行代码。

--- END OF FILE DocAgentLite_Local_V1.1_CodeReady.md ---