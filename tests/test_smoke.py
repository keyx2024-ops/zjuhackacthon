"""核心模块导入与冒烟测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "backend"))


def test_models_import():
    from models.textbook import Textbook, FileFormat, TextbookStatus
    from models.graph import KnowledgePoint, KnowledgeRelation, KnowledgeCategory, RelationType, IntegrationDecision
    from models.rag import DocumentChunk, RAGQuery, RAGResponse, Citation
    from models.dialogue import DialogueSession, DialogueMessage, DialogueIntent

    assert FileFormat.PDF.value == "pdf"
    assert KnowledgeCategory.THEOREM.value == "theorem"
    assert IntegrationDecision.MERGE.value == "merge"


def test_modules_import():
    from modules.file_parser import FileParser
    from modules.knowledge_extractor import KnowledgeExtractor
    from modules.graph_builder import GraphBuilder
    from modules.graph_alignment import GraphAlignment
    from modules.rag_pipeline import RAGPipeline
    from modules.dialogue_agent import DialogueAgent

    assert FileParser is not None
    assert GraphAlignment is not None


def test_prompts_import():
    from prompts.knowledge_extraction import KNOWLEDGE_EXTRACTION_PROMPT
    from prompts.graph_alignment import ALIGNMENT_JUDGE_PROMPT
    from prompts.rag_generation import RAG_GENERATION_PROMPT
    from prompts.dialogue import DIALOGUE_INTENT_PROMPT

    assert "知识点" in KNOWLEDGE_EXTRACTION_PROMPT or "knowledge" in KNOWLEDGE_EXTRACTION_PROMPT.lower()


def test_config():
    from config import settings

    assert 0 < settings.target_compression_ratio <= 1
    assert settings.chunk_size > 0
    assert settings.alignment_similarity_threshold > 0


def test_textbook_model():
    from models.textbook import Textbook, FileFormat, TextbookStatus

    tb = Textbook(name="测试教材", file_format=FileFormat.PDF)
    assert tb.status == TextbookStatus.UPLOADED
    assert tb.textbook_id is not None


def test_knowledge_point_model():
    from models.graph import KnowledgePoint, KnowledgeCategory

    kp = KnowledgePoint(
        name="细胞",
        definition="生命的基本单位",
        category=KnowledgeCategory.CONCEPT,
        textbook_id="tb-1",
    )
    assert kp.frequency == 1
    assert kp.aliases == []
