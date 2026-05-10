"""
多轮对话 API
"""
import logging

from fastapi import APIRouter, HTTPException

from api.store import store
from models.dialogue import DialogueRequest, DialogueResponse
from modules.dialogue_agent import dialogue_agent


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=DialogueResponse)
async def chat(request: DialogueRequest):
    """发送对话消息"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    integration_result = store.get_latest_integration()

    try:
        response = dialogue_agent.chat(request, integration_result)
        if response.graph_updated and integration_result:
            store.add_integration_result(integration_result)
        return response
    except Exception as e:
        logger.error(f"Dialogue failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dialogue failed: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取对话会话历史"""
    session = dialogue_agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.model_dump()
