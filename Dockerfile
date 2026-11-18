FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/opt/huggingface
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
COPY app ./app
COPY chroma_db ./chroma_db
COPY README.md ./README.md
EXPOSE 10000
CMD ["sh","-c","streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-10000} --server.headless=true"]
