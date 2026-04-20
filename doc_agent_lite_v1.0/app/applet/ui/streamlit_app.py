import streamlit as st
import requests
import json
import sseclient
import time
import pandas as pd
import io

API_URL = "http://localhost:8000"

st.set_page_config(page_title="DocAgent Lite v1.1", layout="wide")

st.title("📚 DocAgent Lite V1.1")
st.write("完全本地化的文献挖掘系统 - Powered by qwen2.5:7b")

topic = st.text_input("请输入文献挖掘课题", placeholder="例如: 大模型在医疗领域的应用现状")

if st.button("🚀 开始挖掘"):
    if topic.strip():
        # 1. 提交任务
        resp = requests.post(f"{API_URL}/api/task/start", json={"topic": topic})
        if resp.status_code == 200:
            task_id = resp.json()["task_id"]
            st.session_state["task_id"] = task_id
            st.success(f"任务已创建, ID: {task_id}")
            
            # 2. 状态监听区
            status_container = st.empty()
            log_box = st.empty()
            logs = ""
            
            with st.spinner("流水线正在运行中..."):
                response = requests.get(f"{API_URL}/api/task/{task_id}/stream", stream=True)
                client = sseclient.SSEClient(response)
                
                for event in client.events():
                    log_entry = event.data
                    logs += log_entry + "\n"
                    log_box.code(logs)
                    
                    if "[DONE]" in log_entry or "[ERROR]" in log_entry:
                        break
            
            st.success("流水线执行结束！")
            
            # 获取最终结果
            result_resp = requests.get(f"{API_URL}/api/task/{task_id}/result")
            result = result_resp.json()
            
            if "valid_documents" in result and result["valid_documents"]:
                tab1, tab2 = st.tabs(["📊 情报库", "📥 资料下载"])
                
                with tab1:
                    docs = result["valid_documents"]
                    df = pd.DataFrame([{
                        "文档标题": d["title"],
                        "AI评分": d["score"],
                        "核心亮点": d["summary"],
                        "来源链接": d["url"]
                    } for d in docs])
                    st.dataframe(df, use_container_width=True)
                
                with tab2:
                    st.write("已为您打包好本地Markdown与ChromaDB向量库压缩包：")
                    # FastAPI 提供下载
                    download_url = f"{API_URL}/api/download/{task_id}"
                    zip_response = requests.get(download_url)
                    if zip_response.status_code == 200:
                        st.download_button(
                            label="📦 下载归档资料包 (.zip)",
                            data=zip_response.content,
                            file_name=f"archive_{task_id}.zip",
                            mime="application/zip"
                        )
                    else:
                        st.error("归档包下载失败。")
            else:
                st.warning("未能找到高质量的文档，请更换关键词重试。")
