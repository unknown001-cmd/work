FROM python:3.11-slim

WORKDIR /app

ENV TZ=Asia/Shanghai

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

RUN mkdir -p /app/backend/data

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]