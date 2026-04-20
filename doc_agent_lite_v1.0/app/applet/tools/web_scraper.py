import asyncio
import aiohttp
import urllib.parse
import pdfplumber
import io
from models.schemas import Document
from utils.logger import task_logger

async def fetch_pdf(session, title: str, doc_url: str, task_id: str) -> Document | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (mailto:ffmpeg1024@gmail.com) DocAgent/1.1 Academic-Spider"}
        
        # Scenario 1: It's a direct PDF
        if doc_url.lower().endswith(".pdf"):
            async with session.get(doc_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    pdf_bytes = await response.read()
                    try:
                        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                            text_pages = []
                            for page in pdf.pages[:20]: 
                                extracted = page.extract_text()
                                if extracted:
                                    text_pages.append(extracted)
                            full_text = "\n".join(text_pages)
                            
                        if full_text.strip():
                            task_logger.add_log(task_id, f"[Download] 成功通过源站获取 PDF: {title[:25]}...")
                            return Document(url=doc_url, title=title, content=full_text, raw_file_bytes=pdf_bytes, file_extension=".pdf")
                    except Exception as pdf_err:
                        task_logger.add_log(task_id, f"[Download] 二进制非兼容PDF被跳过: {doc_url[-20:]}")
                else:
                    task_logger.add_log(task_id, f"[Fetch] 源站拒绝访问 PDF {doc_url[-20:]} (HTTP {response.status})")
        
        # Scenario 2: It's a normal HTML webpage or unknown extension
        else:
            jina_url = f"https://r.jina.ai/{doc_url}"
            jina_headers = {"Accept": "application/json"}
            # Jina extraction might take longer, increase timeout to 40s
            async with session.get(jina_url, headers=jina_headers, timeout=40) as response:
                if response.status == 200:
                    data = await response.json()
                    clean_text = data.get("data", {}).get("content", "")
                    actual_title = data.get("data", {}).get("title", title)
                    
                    if clean_text:
                        task_logger.add_log(task_id, f"[Download] 成功通过 Jina 洗白清洗内容: {actual_title[:25]}...")
                        return Document(url=doc_url, title=actual_title, content=clean_text, raw_file_bytes=clean_text.encode('utf-8'), file_extension=".md")
                else:
                    task_logger.add_log(task_id, f"[Fetch] Jina代理抓取失败 {doc_url[-20:]} (HTTP {response.status})")

    except asyncio.TimeoutError:
         task_logger.add_log(task_id, f"[Fetch] 访问超时，源站响应过慢: {doc_url[-20:]}")
    except Exception as e:
         task_logger.add_log(task_id, f"[Fetch] 连接异常 {doc_url[-20:]}: {type(e).__name__}")
    return None


async def concurrent_search_and_fetch(queries: list[str], max_urls_per_query: int = 5, task_id: str = "default") -> list[Document]:
    unique_papers = {} # url -> title
    
    # 禁用 SSL 验证，增加连通率，规避高校学术服务器旧版证书问题
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        # 1. 放弃网页，直接向全球最强开源学术知识图谱 OpenAlex 发起结构化检索请求
        for query in queries:
            try:
                task_logger.add_log(task_id, f"[Search] 正在向 OpenAlex 学术总库请求: {query}")
                encoded_query = urllib.parse.quote(query)
                email = "ffmpeg1024@gmail.com" # 加入 Polite Pool 以获得极速访问
                
                # 关键过滤: is_oa:true 保证有免费 PDF (底层自动连通 Unpaywall)
                api_url = f"https://api.openalex.org/works?search={encoded_query}&filter=is_oa:true,has_abstract:true&per_page={max_urls_per_query + 5}&mailto={email}"
                
                async with session.get(api_url, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        count = 0
                        for res in results:
                            title = res.get("title", "Unknown Title")
                            best_oa = res.get("best_oa_location", {}) or {}
                            pdf_url = best_oa.get("pdf_url")
                            
                            # Unpaywall 数据兜底提取
                            if not pdf_url:
                                oa_info = res.get("open_access", {}) or {}
                                pdf_url = oa_info.get("oa_url")
                            
                            if pdf_url and pdf_url.startswith("http"):
                                if pdf_url not in unique_papers:
                                    unique_papers[pdf_url] = title
                                    count += 1
                                    if count >= max_urls_per_query:
                                        break
                        task_logger.add_log(task_id, f"[Search] '{query}' 找到 {count} 篇附带 OA 完整下载的文献")
                    else:
                        task_logger.add_log(task_id, f"[Search] OpenAlex 请求拦截: HTTP {response.status}")
            except Exception as e:
                task_logger.add_log(task_id, f"[Search] OpenAlex 检索网络异常: {str(e)[:50]}")
                
        urls_to_fetch = list(unique_papers.keys())[:15]
        task_logger.add_log(task_id, f"[Download] 检索完成。准备开辟并发通道直连原始科研机构下载 {len(urls_to_fetch)} 篇 PDF...")
        
        if not urls_to_fetch:
            task_logger.add_log(task_id, "[WARNING] 未找到 OA 学术论文，建议调整为【英文】搜索词提升命中率！")
            return []

        # 2. 并发下载与实控内容清洗
        # 增加信号量（Semaphore）限流，防止瞬间发包过多被 Jina 防火墙与科研高校源站直接阻断请求
        sem = asyncio.Semaphore(4)
        
        async def fetch_with_sem(url):
            async with sem:
                return await fetch_pdf(session, unique_papers[url], url, task_id)
                
        tasks = [fetch_with_sem(url) for url in urls_to_fetch]
        docs = await asyncio.gather(*tasks)
        
    valid_docs = [doc for doc in docs if doc is not None and doc.content]
    task_logger.add_log(task_id, f"[Download] 成功落盘解析 {len(valid_docs)} 篇学术终稿。")
    return valid_docs






