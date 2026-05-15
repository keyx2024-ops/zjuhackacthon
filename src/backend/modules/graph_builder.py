"""
知识图谱构建模块

将提取的知识点和关系组织成结构化的知识图谱
"""
import logging
import uuid
from collections import Counter, defaultdict
from typing import List

from models.graph import KnowledgeGraph, KnowledgePoint, KnowledgeRelation
from models.textbook import Textbook
from modules.knowledge_extractor import knowledge_extractor


logger = logging.getLogger(__name__)


RELATION_LABEL_ZH = {
    "prerequisite": "前置",
    "parallel": "并列",
    "contains": "包含",
    "applies_to": "应用",
    "depends_on": "依赖",
}


class GraphBuilder:
    """知识图谱构建器"""

    def build_from_textbook(self, textbook: Textbook, progress=None) -> KnowledgeGraph:
        """
        从教材构建知识图谱

        Args:
            textbook: 教材对象
            progress: 可选 JobHandle，用于上报进度

        Returns:
            KnowledgeGraph: 知识图谱
        """
        logger.info(f"Building knowledge graph for {textbook.name}")

        points, relations = knowledge_extractor.extract_from_textbook(
            textbook, progress=progress
        )

        points = self._merge_duplicates_within_textbook(points)
        relations = self._dedup_relations(relations)
        statistics = self._compute_statistics(points, relations)

        graph = KnowledgeGraph(
            graph_id=str(uuid.uuid4()),
            textbook_id=textbook.textbook_id,
            is_integrated=False,
            nodes=points,
            edges=relations,
            statistics=statistics,
        )

        logger.info(
            f"Built graph for {textbook.name}: "
            f"{len(points)} nodes, {len(relations)} edges"
        )
        return graph

    def _merge_duplicates_within_textbook(
        self, points: List[KnowledgePoint]
    ) -> List[KnowledgePoint]:
        """合并同一教材内的重复知识点（同名）"""
        name_to_point = {}
        id_to_canonical = {}

        for point in points:
            key = point.name.strip().lower()
            if key in name_to_point:
                canonical = name_to_point[key]
                canonical.frequency += 1
                if point.aliases:
                    canonical.aliases = list(set(canonical.aliases + point.aliases))
                id_to_canonical[point.knowledge_id] = canonical.knowledge_id
            else:
                name_to_point[key] = point
                id_to_canonical[point.knowledge_id] = point.knowledge_id

        return list(name_to_point.values())

    def _dedup_relations(
        self, relations: List[KnowledgeRelation]
    ) -> List[KnowledgeRelation]:
        """去除重复的关系（相同的 source-target-type）"""
        seen = set()
        unique_relations = []
        for rel in relations:
            key = (rel.source_id, rel.target_id, rel.relation_type)
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)
        return unique_relations

    def _compute_statistics(
        self,
        points: List[KnowledgePoint],
        relations: List[KnowledgeRelation],
    ) -> dict:
        """计算图谱统计信息"""
        category_counts = Counter(p.category.value for p in points)

        relation_type_counts = Counter(r.relation_type.value for r in relations)

        degree = defaultdict(int)
        for rel in relations:
            degree[rel.source_id] += 1
            degree[rel.target_id] += 1

        top_central_nodes = []
        if degree:
            sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]
            id_to_name = {p.knowledge_id: p.name for p in points}
            top_central_nodes = [
                {"name": id_to_name.get(node_id, "unknown"), "degree": deg}
                for node_id, deg in sorted_nodes
            ]

        return {
            "total_nodes": len(points),
            "total_edges": len(relations),
            "category_distribution": dict(category_counts),
            "relation_distribution": dict(relation_type_counts),
            "top_central_nodes": top_central_nodes,
            "total_word_count": sum(p.word_count for p in points),
        }

    def to_cytoscape_format(self, graph: KnowledgeGraph) -> dict:
        """
        转换为 Cytoscape.js 可视化格式

        Returns:
            {
                "nodes": [{"data": {...}}, ...],
                "edges": [{"data": {...}}, ...]
            }
        """
        nodes_data = []
        for point in graph.nodes:
            node = {
                "data": {
                    "id": point.knowledge_id,
                    "label": point.name,
                    "category": point.category.value,
                    "definition": point.definition,
                    "textbook_id": point.textbook_id,
                    "textbook_name": point.textbook_name,
                    "chapter_title": point.chapter_title,
                    "page_number": point.page_number,
                    "frequency": point.frequency,
                    "aliases": point.aliases,
                    "size": 20 + min(point.frequency * 5, 30),
                }
            }
            nodes_data.append(node)

        edges_data = []
        for rel in graph.edges:
            rel_en = rel.relation_type.value
            rel_zh = RELATION_LABEL_ZH.get(rel_en, rel_en)
            edge = {
                "data": {
                    "id": rel.relation_id,
                    "source": rel.source_id,
                    "target": rel.target_id,
                    "label": f"{rel_en}\n{rel_zh}",
                    "relation_en": rel_en,
                    "relation_zh": rel_zh,
                    "description": rel.description or "",
                }
            }
            edges_data.append(edge)

        return {
            "nodes": nodes_data,
            "edges": edges_data,
            "statistics": graph.statistics,
        }


graph_builder = GraphBuilder()
