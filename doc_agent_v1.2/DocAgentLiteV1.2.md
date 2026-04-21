--- START OF FILE DocAgent_OSINT_V1.2.md ---
DocAgent OSINT V1.2：专业级开源情报与学术挖掘平台
版本定位：面向硬科技、军工及前沿学术的数字情报分析站。
核心进化：引入多后端专有数据源（学术/新闻网页）、Crawl4AI 现代爬虫引擎、向量+知识图谱（Hybrid RAG）双轨索引，以及反欺骗交叉验证机制。
硬件要求：单机部署，通过模型分时复用与并发控制实现全栈本地化。
一、 OSINT 专属多智能体工作流 (Multi-Agent OSINT Pipeline)
节点 (Node)	Agent 职责定义	技术实现与工具链	V1.2 核心升级点
1. Plan & Route	意图拆解与情报域路由	Qwen2.5-7B (本地)	将单个 Query 路由到四大域：Academic(学术), Patent(专利), Forum(论坛), News(公开网络)
2. Multi-Search	无算力并发探针	Python 异步协程	接入 OpenAlex API (学术连通图), Google Patents (工艺图纸), DuckDuckGo (Site限定搜索)
3. Deep Scrape	绕过反爬与清洗	Crawl4AI (本地运行)	废弃老旧爬虫。自动执行 JS 渲染，剔除广告，直接输出对 LLM 极其友好的高纯净度 Markdown。
4. Vector Dedup	语义级去重降噪	bge-m3 (本地 Embedding)	在喂给大模型前，计算余弦相似度，合并重合度 > 90% 的文章，极大节省后续 GPU 算力。
5. Enrich & Graph	情报浓缩与实体抽提	Qwen2.5-7B (带并发锁)	截断阅读单篇文章。不仅打分，还提取关系三元组 (如 [机构A]-研发->[技术B])，构建轻量情报图谱。
6. Cross-Examine	红蓝对抗 (交叉验证)	Qwen2.5-7B (独立 Prompt)	审视所有高分情报，寻找矛盾点（如：A文说已量产，B文说被禁运），标记置信度。
7. Hybrid Index	双轨物理归档	ChromaDB + Kùzu DB	同时落盘向量数据库与本地轻量级图数据库。并提供 Zip 源码打包。
二、 系统架构流转图 (System Architecture)
code
Mermaid
graph TD
    subgraph 用户与呈现层 (Streamlit UI)
        U1[输入: 隐身战机单光子雷达] --> U2[SSE 情报流控面板]
        U2 --> U3[🎯 交付区]
        U3 --> T1[📊 高价值情报卡片]
        U3 --> T2[🕸️ 实体关系网络图 (Knowledge Graph)]
        U3 --> T3[⚠️ 矛盾与置信度预警分析]
        U3 --> T4[📦 本地物理快照下载]
    end

    U1 --> B[FastAPI Gateway] --> C[LangGraph Orchestrator]

    subgraph 1. 广域探测层 (Multi-Backend)
        C -->|路由| D1[OpenAlex/arXiv API<br/>引文网络挖掘]
        C -->|路由| D2[Espacenet/Patents API<br/>底层工艺挖掘]
        C -->|路由| D3[DDG site:特定论坛/机构<br/>暗数据探测]
    end

    subgraph 2. 深度提取层 (Deep Scrape)
        D1 & D2 & D3 --> E[Crawl4AI Engine <br/> 无头浏览器 + 防封锁]
        E -->|净化后的 Markdown / PDF| F[bge-m3 向量去重过滤]
    end

    subgraph 3. 情报推理层 (Local GPU)
        F -->|过滤后的核心文本| G[Enrichment Agent <br/> qwen2.5:7b]
        G -->|生成三元组 & 评分| H{Cross-Examination <br/> 红蓝对抗机制}
        H -->|发现数据冲突/确认高价值| I[Hybrid Archive Node]
    end

    subgraph 4. 本地物理资产 (Storage)
        I -.-> S1[(ChromaDB<br/>语义检索库)]
        I -.-> S2[(Kùzu DB<br/>本地图数据库)]
        I -.-> S3[📁 /archives<br/>纯文本与源文件]
    end
三、 V1.2 核心技术落地规范 (Engineering Hacks)
为了在单卡 24G 跑通这个宏大的 OSINT 架构，必须实施以下工程限制：
1. 多后端路由机制 (Multi-Backend Routing)
摒弃单一的 Tavily，针对特定专业词汇执行定向打击。
code
Python
# agents/plan_node.py
def route_queries(topic: str, llm):
    # LLM 返回 JSON 路由表
    # 示例输出：
    return {
        "academic": ["SPAD compact LiDAR", "single-photon avalanche diode array"],
        "patent": ["compact SPAD array patent", "单光子探测器 封装工艺"],
        "forum": ["site:zhihu.com 单光子探测 军工", "site:defencehub.live SPAD"]
    }
2. Crawl4AI 的无缝集成 (替代旧版 Scraper)
这是目前最强大的现代爬虫。它能把乱七八糟的网页直接变成干净的 Markdown。
code
Python
# tools/modern_scraper.py
from crawl4ai import AsyncWebCrawler

async def deep_scrape_url(url: str) -> str:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            word_count_threshold=50,       # 过滤掉内容极少的垃圾网页
            exclude_external_links=True,   # 剔除广告外链
            bypass_cache=True
        )
        return result.markdown             # 直接返回 LLM 友好的 Markdown
3. 轻量化 GraphRAG 实体抽取 (防显存溢出)
传统的 GraphRAG 会消耗极其庞大的 Token。在 V1.2 中，我们采用随文抽提法 (In-flight Extraction)。
在 Evaluate 节点打分的同时，顺便抽取 3-5 个核心实体，写入本地最轻量的图数据库 Kùzu（完全无服务端依赖，类似 SQLite）。
code
Python
# models/schemas.py (Pydantic约束)
class OSINT_Extraction(BaseModel):
    is_relevant: bool
    score: int
    summary: str
    entities_and_relations: List[List[str]] = Field(
        description="返回三元组，格式为 ['实体1', '关系', '实体2']。例如 ['机构A', '研发了', 'SPAD探测器']"
    )
4. 红蓝对抗防欺骗 (Cross-Examination Node)
针对极具战略价值的情报，系统会自动比对。
code
Python
# agents/cross_examine_node.py
def cross_examine(state: AgentState):
    # 汇总所有 Enrich 节点产出的 Summary
    summaries = [doc.summary for doc in state.valid_documents]
    
    prompt = f"""作为红蓝对抗分析师，请审查以下获取的情报片段集合：
    {summaries}
    
    任务：找出这些情报中是否存在互相矛盾、存疑或过度夸大的技术指标。
    如果没有矛盾，请输出 '置信度高'。如果有矛盾，请指出。"""
    
    conflict_report = llm.invoke(prompt)
    return {"conflict_report": conflict_report}
四、 项目目录结构（V1.2 OSINT 增强版）
新增了针对专利、学术的 API 封装，并集成了图数据库驱动。
code
Text
doc_agent_osint_v1.2/
├── requirements.txt             # 新增: crawl4ai, kuzu, pyalex (OpenAlex SDK)
├── config.yaml                  # 各类 API Key (如有) 与 并发控制阈值
├── main.py                      # FastAPI网关
├── agents/
│   ├── graph.py                 # 包含路由选择与红蓝对抗的新版 LangGraph 连线
│   ├── nodes_search.py          # 包含 Academic, Patent, Web 三大探测器
│   ├── nodes_evaluate.py        # 包含向量去重、截断评估与知识图谱抽取
│   └── nodes_examine.py         # 新增: 交叉验证节点
├── models/
│   └── schemas.py               # 增加 OSINT_Extraction 模型 (带三元组)
├── tools/
│   ├── modern_scraper.py        # Crawl4AI 深度清洗爬虫封装
│   ├── vector_store.py          # 本地 ChromaDB 封装
│   └── graph_store.py           # 本地 Kùzu 图数据库封装 (存放三元组)
├── storage/
│   ├── archives/                
│   ├── chroma_db/               
│   └── kuzu_db/                 # 新增: 本地物理图数据库目录
└── ui/
    └── streamlit_app.py         # 新增 Tab: 实体关系网图谱展示 (使用 pyvis 渲染)
--- END OF FILE DocAgent_OSINT_V1.2.md ---