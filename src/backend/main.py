"""
FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from api import textbook, graph, integration, rag, dialogue


logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Knowledge Integration Agent...")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path("./logs").mkdir(parents=True, exist_ok=True)

    logger.info("Application started successfully")
    yield

    logger.info("Shutting down Knowledge Integration Agent...")


app = FastAPI(
    title="学科知识整合智能体",
    description="基于 AI 的学科知识整合系统",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(textbook.router, prefix="/api/textbooks", tags=["教材管理"])
app.include_router(graph.router, prefix="/api/graphs", tags=["知识图谱"])
app.include_router(integration.router, prefix="/api/integration", tags=["整合操作"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG 问答"])
app.include_router(dialogue.router, prefix="/api/dialogue", tags=["多轮对话"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "学科知识整合智能体 API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )
