from fastapi import FastAPI

app = FastAPI(title="Board Game Ranker API")

# Подключаем API роутеры
from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}

# Start the server
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)