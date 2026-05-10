"""
教材管理 API
"""
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.store import store
from config import settings
from models.textbook import TextbookList, TextbookStatus, TextbookUploadResponse
from modules.file_parser import file_parser


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=TextbookUploadResponse)
async def upload_textbook(file: UploadFile = File(...)):
    """上传教材文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_size = 0
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    file_path = upload_dir / f"{file_id}_{file.filename}"

    try:
        with file_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > settings.max_upload_size:
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File too large")
                f.write(chunk)

        textbook = file_parser.parse(str(file_path), textbook_name=Path(file.filename).stem)
        store.add_textbook(textbook)

        return TextbookUploadResponse(
            textbook_id=textbook.textbook_id,
            name=textbook.name,
            status=textbook.status,
            message=f"成功解析 {len(textbook.chapters)} 个章节，{textbook.total_words} 字",
        )

    except ValueError as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("", response_model=TextbookList)
async def list_textbooks():
    """获取教材列表"""
    textbooks = store.list_textbooks()
    return TextbookList(total=len(textbooks), textbooks=textbooks)


@router.get("/{textbook_id}")
async def get_textbook(textbook_id: str):
    """获取教材详情"""
    textbook = store.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=404, detail="Textbook not found")
    return textbook


@router.delete("/{textbook_id}")
async def delete_textbook(textbook_id: str):
    """删除教材"""
    textbook = store.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=404, detail="Textbook not found")

    file_path = Path(textbook.file_path)
    file_path.unlink(missing_ok=True)
    store.remove_textbook(textbook_id)

    return {"message": "Textbook deleted successfully"}
