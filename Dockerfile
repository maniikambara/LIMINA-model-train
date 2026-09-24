# Image untuk api/ (FastAPI). output/*.joblib sudah ter-commit oleh
# retrain-random-forest.yml (lihat docs/PANDUAN-FASTAPI.md Bagian 5),
# jadi COPY . . di bawah otomatis menyertakannya kalau image ini dibangun
# dari checkout git yang sudah pernah kena retrain minimal sekali.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
