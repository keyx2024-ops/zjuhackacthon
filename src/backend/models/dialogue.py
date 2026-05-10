"""
对话数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DialogueIntent(str, Enum):
    """对话意图"""
    QUERY = "query"
    MODIFY_DECISION = "modify_decision"
    EXPLAIN_DECISION = "explain_decision"
    REVIEW_GRAPH = "review_graph"
    GENERAL = "general"


class DialogueMessage(BaseModel):
    """对话消息"""
    message_id: str
    role: MessageRole
    content: str
    intent: Optional[DialogueIntent] = None
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class DialogueSession(BaseModel):
    """对话会话"""
    session_id: str
    user_id: Optional[str] = None
    messages: List[DialogueMessage] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DialogueRequest(BaseModel):
    """对话请求"""
    session_id: Optional[str] = None
    message: str
    context: dict = Field(default_factory=dict)


class DialogueResponse(BaseModel):
    """对话响应"""
    session_id: str
    message: DialogueMessage
    actions_taken: List[str] = Field(default_factory=list)
    graph_updated: bool = False
    updated_graph_id: Optional[str] = None
