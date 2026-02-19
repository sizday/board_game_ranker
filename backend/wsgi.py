print("🚀 STARTING WSGI.PY", flush=True)

from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="Board Game Ranker API")

# Подключаем API роутеры
app.include_router(api_router, prefix="/api")

print("✅ FASTAPI APP WITH ROUTERS CREATED", flush=True)

@app.get("/health")
def health():
    return {"status": "ok"}

# Start the server
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)