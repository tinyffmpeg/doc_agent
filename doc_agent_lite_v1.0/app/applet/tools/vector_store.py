import os
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

def vectorize_and_store(task_id: str, valid_documents: list, base_url: str, model: str):
    persist_directory = f"storage/archives/{task_id}/chroma_db"
    os.makedirs(persist_directory, exist_ok=True)
    
    # langchain_community 的 OllamaEmbeddings 使用的是 Ollama 原生的 /api/embeddings 接口
    # 而由于在配置档里 llm.base_url 尾部带有 "/v1" 给基于 OpenAI 规范的节点使用，
    # OllamaEmbeddings 并接上 /api 时变成了 /v1/api/embeddings 导致触发 HTTP 404
    clean_base_url = base_url.replace("/v1", "").rstrip("/")
    embeddings = OllamaEmbeddings(model=model, base_url=clean_base_url)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    
    lc_docs = []
    for doc in valid_documents:
        lc_docs.append(LCDocument(page_content=doc.content, metadata={"url": doc.url, "title": doc.title}))
        
    split_docs = text_splitter.split_documents(lc_docs)
    
    if split_docs:
        Chroma.from_documents(documents=split_docs, embedding=embeddings, persist_directory=persist_directory)
    return persist_directory

