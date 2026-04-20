#!/bin/bash
pip install -r requirements.txt

# Run FastAPI backend in background
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Run Streamlit frontend in foreground (port 3000 for exposure)
python3 -m streamlit run ui/streamlit_app.py --server.port 3000 --server.address 0.0.0.0
