FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install uv && uv pip install --system --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8091
CMD ["python", "main.py"]
