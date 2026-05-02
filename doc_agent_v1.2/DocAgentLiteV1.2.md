
--- START OF FILE DocAgent_OSINT_V1.3.md ---
# DocAgent OSINT V1.2：专业级开源情报与学术挖掘平台

**版本定位**：面向硬科技、军工及前沿学术的数字情报分析站。
**核心进化 (V1.2)**：引入 **SearXNG 元搜索代理**绕过反爬、**SimHash+向量双阶去重**规避高优情报误删、基于 **vLLM 连续批处理**的单卡 24G 极限并发、以及基于**强约束本体库 (Ontology)** 的图数据库实体消歧与精准防欺骗对抗。
**硬件要求**：单机 24G 显存 (如 RTX 3090/4090)，全栈本地化断网可用。

---

### 一、 OSINT 专属多智能体工作流 (Multi-Agent OSINT Pipeline)

| 节点 (Node) | Agent 职责定义 | 技术实现与工具链 | V1.2 核心升级点 |
| :--- | :--- | :--- | :--- |
| **1. Plan & Route** | 意图拆解与情报域路由 | Qwen2.5-7B (本地) | 将单个 Query 路由到四大域：Academic(学术), Patent(专利), Forum(论坛), News(公开网络) |
| **2. Multi-Search** | 无算力并发探针 | Python 异步 + **SearXNG** | 接入 OpenAlex (学术连通图), Google Patents (工艺), **引入本地 SearXNG 聚合搜索，彻底解决单 IP 被拦截问题**。 |
| **3. Deep Scrape** | 绕过反爬与深度清洗 | Crawl4AI (本地无头) | 自动执行 JS 渲染，剔除广告与 DOM 噪音，直接输出高纯净度 Markdown。 |
| **4. Text Dedup** | 字面与语义双阶降噪 | **SimHash** + bge-m3 | **废弃纯向量去重。** 先用 SimHash (阈值>95%) 剔除洗稿/转载；bge-m3 仅负责切片并向量化入库，杜绝高相似度异构情报被误删。 |
| **5. Enrich & Graph** | 硬核指标与实体抽提 | Qwen2.5-7B (结构化输出) | 截断阅读长文。**强制采用白名单谓语**，提取标准化三元组；并提取包含具体数据的声明 (Claims) 备用。 |
| **6. Cross-Examine** | 红蓝对抗 (交叉验证) | Qwen2.5-7B (独立 Prompt) | **废弃摘要对比。** 直接拉取各路信源提取出的“技术指标 (Claims)”进行数值/进度比对，精准发现情报矛盾点。 |
| **7. Hybrid Index** | 双轨物理归档 | ChromaDB + Kùzu DB | 同时落盘向量数据库 (供 RAG) 与本地图数据库 (Kùzu)。提供 Zip 源码打包。 |

---

### 二、 系统架构流转图 (System Architecture)

```mermaid
graph TD
    subgraph 用户与呈现层 (Streamlit UI)
        U1[输入: 隐身战机单光子雷达] --> U2[SSE 情报流控面板]
        U2 --> U3[🎯 交付区]
        U3 --> T1[📊 高价值情报卡片]
        U3 --> T2[🕸️ 实体关系网络图 (精准消歧版)]
        U3 --> T3[⚠️ 矛盾与置信度预警分析]
        U3 --> T4[📦 本地物理快照下载]
    end

    U1 --> B[FastAPI Gateway] --> C[LangGraph Orchestrator]

    subgraph 1. 广域探测层 (Multi-Backend)
        C -->|路由| D1[OpenAlex/arXiv API<br/>引文网络挖掘]
        C -->|路由| D2[Espacenet/Patents API<br/>底层工艺挖掘]
        C -->|路由| D3[SearXNG 聚合搜索<br/>代理分发绕过反爬]
    end

    subgraph 2. 深度清洗与去重层 (Clean & Dedup)
        D1 & D2 & D3 --> E[Crawl4AI Engine <br/> 无头浏览器 JS渲染]
        E -->|Markdown 纯净文本| F1[SimHash 过滤高度洗稿文]
        F1 -->|独立信源| F2[bge-m3 语义切片入库]
    end

    subgraph 3. 情报推理层 (Local GPU: vLLM 统一显存管理)
        F2 -->|核心文本切片| G[Enrichment Agent <br/> 连续批处理并发]
        G -->|输出硬核事实 Claims <br/> & 规范化三元组| H{Cross-Examination <br/> 基于具体数值/指标对抗}
        H -->|发现数据冲突/确认高价值| I[Hybrid Archive Node]
    end

    subgraph 4. 本地物理资产 (Storage)
        I -.-> S1[(ChromaDB<br/>语义检索库)]
        I -.-> S2[(Kùzu DB<br/>本地图数据库)]
        I -.-> S3[📁 /archives<br/>纯文本与源文件]
    end
```

---

### 三、 V1.2 核心技术落地规范 (Engineering Hacks)

为了在单卡 **24G 显存** 下支撑起高并发的复杂 OSINT 工作流，必须实施以下极端的工程级优化与重构：

#### 1. 显存复用与连续批处理 (Continuous Batching)
严禁在 LangGraph 的不同 Agent 节点中单独实例化、加锁或加载 LLM。
**规范**：底层采用 `vLLM`（或 Ollama）加载 `Qwen2.5-7B-Instruct-AWQ` (4-bit 量化，仅占 ~5.5GB 显存)。释放出多达 15GB+ 的显存用于维护庞大的 KV Cache。FastAPI 将所有智能体的并发请求通过 OpenAI 兼容 API 发给 vLLM，利用 PagedAttention 实现极高吞吐的无锁并发，同时保证给 Crawl4AI 留下足够的内存跑无头浏览器。

#### 2. 本体库强约束防图谱灾难 (Ontology-Constrained GraphRAG)
若任由大模型自由发散抽取实体，会导致图数据库变成充满同义词和冗余关系的“垃圾场”。必须通过 Pydantic 对实体类型和谓语关系施加**白名单级约束**。

```python
# models/schemas.py (Pydantic 结构化输出)
from pydantic import BaseModel, Field
from typing import List

class FactTriple(BaseModel):
    subject: str = Field(description="主语，必须为具体实体全称，如 'Lockheed Martin'")
    # 强制限定谓语类型，防止生成无限多样的同义词关系
    predicate: str = Field(description="谓语，必须是以下之一：[开发, 投资, 量产, 性能指标, 合作, 使用, 竞争, 采购]")
    object: str = Field(description="宾语，如具体的指标数字(500km)、型号(F-35)或另一机构")

class OSINT_Extraction(BaseModel):
    is_relevant: bool
    score: int
    # 核心：专门提取包含时间、数据、型号等客观事实的原话，为后续打下基础
    claims: List[str] = Field(description="提取包含具体数字、指标、时间节点的硬核陈述语句")
    entities_and_relations: List[FactTriple] 
```

#### 3. 基于“硬事实”的红蓝对抗 (Cross-Examination)
将上一步抽取出的所有孤立的 `claims` 汇聚，让大模型直接就**硬核指标**进行查证。

```python
# agents/cross_examine_node.py
def cross_examine(state: AgentState):
    # 提取所有信源中的“事实声明 (Claims)”，而非模糊的 Summary
    all_claims = [claim for doc in state.valid_documents for claim in doc.claims]
    
    prompt = f"""作为红蓝对抗情报分析师，请审查以下提取的技术指标与事实声明池：
    {all_claims}
    
    任务：
    1. 寻找数值冲突（如：A信源说重量是50kg，B信源说70kg）。
    2. 寻找进度冲突（如：A称项目处于实验室阶段，B称已量产军方采购）。
    若存在矛盾，请输出结构化的 <Conflict_Report> 指明冲突点及来源；若一致，输出对该情报的置信度。"""
    
    conflict_report = vllm_client.invoke(prompt)
    return {"conflict_report": conflict_report}
```

#### 4. 双阶文本去重 (SimHash)
**规范**：
1. **字面级去重**：使用 `SimHash` 计算文章指纹，汉明距离极小（如重合度>95%）直接判定为通稿、洗稿并丢弃。
2. **向量化**：仅将经过字面去重的独立信源文本送入 `bge-m3` 计算向量落盘 ChromaDB。

#### 5. SearXNG 元搜索与 Crawl4AI 现代爬虫引擎
*   **SearXNG**：代理并打散对 Google, Bing, DDG, 垂直论坛的请求，防止高频自动化搜索触发 Captcha 验证。
*   **Crawl4AI**：替代传统的 BeautifulSoup。异步运行无头浏览器，等待目标网站的 JS 框架完全渲染（如各类学术站点、政府官网），并在生成给 LLM 阅读前直接转换为规整的 Markdown。

---

### 四、 项目目录结构（V1.3 OSINT）

```text
doc_agent_osint_v1.3/
├── requirements.txt             # 新增: vllm, crawl4ai, kuzu, simhash, pyalex
├── config.yaml                  # SearXNG 端口, LLM Backend IP, 并发与阈值配置
├── main.py                      # FastAPI网关
├── agents/
│   ├── graph.py                 # LangGraph 工作流定义与状态机
│   ├── nodes_search.py          # 包含 SearXNG, OpenAlex, Patents 探针
│   ├── nodes_evaluate.py        # 强约束的 Ontology 信息抽取节点
│   └── nodes_examine.py         # 新增: 基于 Claims 的数值级红蓝对抗节点
├── models/
│   └── schemas.py               # 强类型 Pydantic 模型 (FactTriple, Claims)
├── tools/
│   ├── modern_scraper.py        # Crawl4AI JS渲染及反反爬封装
│   ├── text_dedup.py            # 新增: 基于 SimHash 的防洗稿文本去重模块
│   ├── vector_store.py          # 本地 ChromaDB (bge-m3 向量切片封装)
│   └── graph_store.py           # 本地 Kùzu 极速图数据库封装
├── storage/
│   ├── archives/                # 纯文本与源文件 (.md / .pdf)
│   ├── chroma_db/               # 语义检索索引物理落盘
│   └── kuzu_db/                 # 实体关系网图谱物理落盘
└── ui/
    └── streamlit_app.py         # SSE 情报流控 UI & pyvis 图谱动态渲染
```
--- END OF FILE DocAgent_OSINT_V1.2.md ---