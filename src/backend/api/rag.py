"""
RAG 问答 API
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.store import store
from models.rag import RAGQuery, RAGResponse
from modules.rag_pipeline import rag_pipeline


logger = logging.getLogger(__name__)
router = APIRouter()


class IndexRequest(BaseModel):
    textbook_ids: List[str]


@router.post("/index")
async def build_index(request: IndexRequest):
    """为教材建立向量索引"""
    indexed_count = 0
    skipped_ids = []
    for textbook_id in request.textbook_ids:
        textbook = store.get_textbook(textbook_id)
        if not textbook:
            raise HTTPException(
                status_code=404, detail=f"Textbook not found: {textbook_id}"
            )
        chunks_added = rag_pipeline.index_textbook(textbook)
        indexed_count += chunks_added
        if chunks_added == 0:
            skipped_ids.append(textbook_id)

    status = rag_pipeline.get_status()
    return {
        "message": f"Indexed {indexed_count} new chunks",
        "skipped_textbook_ids": skipped_ids,
        "status": status.model_dump(),
    }


@router.post("/query", response_model=RAGResponse)
async def query(rag_query: RAGQuery):
    """RAG 问答"""
    if not rag_query.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        return rag_pipeline.query(rag_query)
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/status")
async def get_status():
    """获取索引状态"""
    return rag_pipeline.get_status()
