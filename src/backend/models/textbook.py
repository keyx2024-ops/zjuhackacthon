"""
教材数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class FileFormat(str, Enum):
    """支持的文件格式"""
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"
    TXT = "txt"


class TextbookStatus(str, Enum):
    """教材处理状态"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    INDEXED = "indexed"
    FAILED = "failed"


class Chapter(BaseModel):
    """章节"""
    chapter_id: str
    chapter_number: str
    title: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    word_count: int = 0


class Textbook(BaseModel):
    """教材"""
    textbook_id: str
    name: str
    file_format: FileFormat
    file_size: int
    file_path: str
    status: TextbookStatus = TextbookStatus.UPLOADED
    total_pages: int = 0
    total_words: int = 0
    chapters: List[Chapter] = Field(default_factory=list)
    upload_time: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class TextbookUploadResponse(BaseModel):
    """教材上传响应"""
    textbook_id: str
    name: str
    status: TextbookStatus
    message: str
    job_id: Optional[str] = None


class TextbookList(BaseModel):
    """教材列表"""
    total: int
    textbooks: List[Textbook]
