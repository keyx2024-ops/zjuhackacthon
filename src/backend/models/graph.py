"""
知识图谱数据模型
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeCategory(str, Enum):
    """知识点类别"""
    CONCEPT = "concept"
    THEOREM = "theorem"
    METHOD = "method"
    EXAMPLE = "example"
    APPLICATION = "application"
    DEFINITION = "definition"


class RelationType(str, Enum):
    """关系类型"""
    PREREQUISITE = "prerequisite"
    PARALLEL = "parallel"
    CONTAINS = "contains"
    APPLIES_TO = "applies_to"
    DEPENDS_ON = "depends_on"
    SIMILAR_TO = "similar_to"


class IntegrationDecision(str, Enum):
    """整合决策类型"""
    MERGE = "merge"
    KEEP = "keep"
    REMOVE = "remove"


class KnowledgePoint(BaseModel):
    """知识点"""
    knowledge_id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    definition: str
    category: KnowledgeCategory
    textbook_id: str
    textbook_name: str
    chapter_id: str
    chapter_title: str
    page_number: Optional[int] = None
    original_text: Optional[str] = None
    word_count: int = 0
    embedding: Optional[List[float]] = None
    frequency: int = 1
    metadata: dict = Field(default_factory=dict)


class KnowledgeRelation(BaseModel):
    """知识点关系"""
    relation_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    description: Optional[str] = None
    confidence: float = 1.0
    metadata: dict = Field(default_factory=dict)


class KnowledgeGraph(BaseModel):
    """知识图谱"""
    graph_id: str
    textbook_id: Optional[str] = None
    is_integrated: bool = False
    nodes: List[KnowledgePoint] = Field(default_factory=list)
    edges: List[KnowledgeRelation] = Field(default_factory=list)
    statistics: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class IntegrationAction(BaseModel):
    """整合操作"""
    action_id: str
    decision: IntegrationDecision
    primary_knowledge_id: str
    secondary_knowledge_ids: List[str] = Field(default_factory=list)
    reason: str
    similarity_score: Optional[float] = None
    llm_confidence: Optional[float] = None
    is_user_modified: bool = False


class IntegrationResult(BaseModel):
    """整合结果"""
    result_id: str
    textbook_ids: List[str]
    # 原始 N 本教材的总字数（赛题分母）
    original_total_words: int
    # 整合后精华版本的总字数（知识点定义合计）
    integrated_total_words: int
    # 压缩比 = integrated_total_words / original_total_words（赛题口径）
    compression_ratio: float
    # 用户在本次整合中设定的目标压缩比
    target_ratio: float = 0.30
    # 知识点级别的辅助指标
    original_kp_count: int = 0
    integrated_kp_count: int = 0
    decisions: List[IntegrationAction]
    integrated_graph: KnowledgeGraph
    created_at: datetime = Field(default_factory=datetime.now)
