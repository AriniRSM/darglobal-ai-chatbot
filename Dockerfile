FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/opt/huggingface
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0+cpu \
    && pip install -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
COPY app ./app
COPY .streamlit ./.streamlit
COPY data/scraped ./data/scraped
RUN HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m app.ingestion.pipeline
COPY README.md ./README.md
EXPOSE 10000
CMD ["sh","-c","PYTHONPATH=/app streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-10000} --server.headless=true"]
