from fastapi import FastAPI
from src.infrastructure.api import router

app = FastAPI(
    title="Sistema de Gestión de Órdenes de Reparación",
    description="API para administrar el ciclo de vida de órdenes de reparación de vehículos",
    version="1.0.0"
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
