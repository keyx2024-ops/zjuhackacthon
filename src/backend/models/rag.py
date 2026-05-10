"""
RAG 数据模型
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """文档分块"""
    chunk_id: str
    content: str
    textbook_id: str
    textbook_name: str
    chapter_id: str
    chapter_title: str
    page_number: Optional[int] = None
    chunk_index: int = 0
    word_count: int = 0
    embedding: Optional[List[float]] = None
    metadata: dict = Field(default_factory=dict)


class Citation(BaseModel):
    """引用来源"""
    chunk_id: str
    textbook_name: str
    chapter_title: str
    page_number: Optional[int] = None
    relevance_score: float = 0.0
    text_snippet: str = ""


class RAGQuery(BaseModel):
    """RAG 查询"""
    query: str
    top_k: int = 5
    use_rerank: bool = True
    use_hybrid_search: bool = True
    textbook_ids: Optional[List[str]] = None


class RAGResponse(BaseModel):
    """RAG 响应"""
    query: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    retrieval_time: float = 0.0
    generation_time: float = 0.0
    total_time: float = 0.0
    token_usage: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class IndexStatus(BaseModel):
    """索引状态"""
    total_documents: int = 0
    total_chunks: int = 0
    total_textbooks: int = 0
    embedding_model: str = ""
    index_size: int = 0
    last_updated: Optional[datetime] = None


class BenchmarkQuestion(BaseModel):
    """RAG Benchmark 测试问题"""
    question_id: str
    question: str
    expected_answer: str
    expected_citations: List[str] = Field(default_factory=list)
    category: str = ""
    difficulty: str = "medium"
