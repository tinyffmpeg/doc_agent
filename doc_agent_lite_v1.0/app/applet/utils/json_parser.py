import re
import json
import logging

def parse_qwen_json(text: str) -> dict | list:
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
