"""
跨教材知识图谱整合模块（核心难点）

实现双重对齐策略：
1. 第一层：Embedding 计算语义相似度（快速筛选）
2. 第二层：LLM 判断是否等价（精准判定）
3. 整合决策：merge / keep / remove
4. 压缩比控制：≤30%
"""
import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings
from models.graph import (
    IntegrationAction,
    IntegrationDecision,
    IntegrationResult,
    KnowledgeGraph,
    KnowledgePoint,
    KnowledgeRelation,
)
from modules.llm_client import llm_client
from prompts.graph_alignment import build_alignment_prompt


logger = logging.getLogger(__name__)


ALIGN_LLM_CONCURRENCY = 5


class GraphAlignment:
    """图谱对齐与整合"""

    def __init__(self):
        self.embedding_model = None
        self.client = llm_client
        self.similarity_threshold = settings.alignment_similarity_threshold
        self.target_compression = settings.target_compression_ratio

    def _get_embedding_model(self):
        """懒加载 embedding 模型"""
        if self.embedding_model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self.embedding_model = SentenceTransformer(
                settings.embedding_model, device=settings.embedding_device
            )
        return self.embedding_model

    def integrate(
        self,
        graphs: List[KnowledgeGraph],
        textbook_total_words: int = 0,
        target_ratio: float = None,
        progress=None,
    ) -> IntegrationResult:
        """整合多本教材的知识图谱

        Args:
            graphs: 各本教材的知识图谱
            textbook_total_words: 原始教材总字数（赛题压缩比分母）
            target_ratio: 目标压缩比，默认取 settings.target_compression_ratio
            progress: 进度回调
        """
        if len(graphs) < 2:
            raise ValueError("Integration requires at least 2 graphs")

        if target_ratio is None or target_ratio <= 0:
            target_ratio = self.target_compression
        target_ratio = max(0.01, min(target_ratio, 1.0))

        logger.info(
            f"Integrating {len(graphs)} graphs, target_ratio={target_ratio:.2%}"
        )

        all_points = []
        for graph in graphs:
            all_points.extend(graph.nodes)

        if textbook_total_words <= 0:
            textbook_total_words = sum(p.word_count for p in all_points)
            logger.warning(
                "textbook_total_words not provided, falling back to KP-level sum"
            )

        kp_total_words = sum(p.word_count for p in all_points)
        logger.info(
            f"Total KPs: {len(all_points)}, KP words: {kp_total_words}, "
            f"textbook words: {textbook_total_words}"
        )

        if progress:
            progress.update(
                phase="计算知识点 Embedding",
                current=10,
                total=100,
                message=f"共 {len(all_points)} 个知识点",
            )

        candidate_pairs = self._embedding_alignment(all_points)
        logger.info(f"Found {len(candidate_pairs)} candidate alignment pairs")
        if progress:
            progress.update(
                phase="LLM 判等",
                current=30,
                total=100,
                message=f"候选对 {len(candidate_pairs)} 对",
            )

        equivalent_groups = self._llm_alignment(all_points, candidate_pairs, progress=progress)
        logger.info(f"Confirmed {len(equivalent_groups)} equivalent groups")

        if progress:
            progress.update(phase="生成整合决策", current=85, total=100, message="构建合并图谱")

        decisions = self._make_decisions(
            all_points, equivalent_groups, textbook_total_words, target_ratio
        )
        integrated_graph = self._build_integrated_graph(all_points, decisions, graphs)

        integrated_words = sum(p.word_count for p in integrated_graph.nodes)
        compression_ratio = (
            integrated_words / textbook_total_words if textbook_total_words > 0 else 0
        )

        logger.info(
            f"Integration complete: integrated={integrated_words} / textbook={textbook_total_words}, "
            f"compression_ratio={compression_ratio:.2%} (target={target_ratio:.2%})"
        )
        if progress:
            progress.update(current=100, total=100, message="完成")

        result = IntegrationResult(
            result_id=str(uuid.uuid4()),
            textbook_ids=[g.textbook_id for g in graphs if g.textbook_id],
            original_total_words=textbook_total_words,
            integrated_total_words=integrated_words,
            compression_ratio=compression_ratio,
            target_ratio=target_ratio,
            original_kp_count=len(all_points),
            integrated_kp_count=len(integrated_graph.nodes),
            decisions=decisions,
            integrated_graph=integrated_graph,
        )

        return result

    def _embedding_alignment(
        self, points: List[KnowledgePoint]
    ) -> List[Tuple[int, int, float]]:
        """
        第一层对齐：使用 Embedding 计算相似度

        Returns:
            候选对列表 [(idx_a, idx_b, similarity), ...]
        """
        model = self._get_embedding_model()
        texts = [f"{p.name}：{p.definition}" for p in points]

        logger.info(f"Computing embeddings for {len(texts)} knowledge points")
        embeddings = model.encode(
            texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        )

        candidate_pairs = []
        embeddings_np = np.array(embeddings)
        similarity_matrix = embeddings_np @ embeddings_np.T

        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if points[i].textbook_id == points[j].textbook_id:
                    continue

                similarity = float(similarity_matrix[i, j])
                if similarity >= self.similarity_threshold:
                    candidate_pairs.append((i, j, similarity))

        candidate_pairs.sort(key=lambda x: x[2], reverse=True)
        return candidate_pairs

    def _llm_alignment(
        self,
        points: List[KnowledgePoint],
        candidate_pairs: List[Tuple[int, int, float]],
        progress=None,
    ) -> List[List[int]]:
        """第二层对齐：使用 LLM 判断是否等价（并发）"""
        parent = list(range(len(points)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        if not candidate_pairs:
            return []

        n_pairs = len(candidate_pairs)
        results: Dict[int, bool] = {}

        with ThreadPoolExecutor(max_workers=ALIGN_LLM_CONCURRENCY) as pool:
            future_to_idx = {
                pool.submit(
                    self._llm_judge_equivalence, points[a], points[b], sim
                ): k
                for k, (a, b, sim) in enumerate(candidate_pairs)
            }
            done = 0
            for fut in as_completed(future_to_idx):
                k = future_to_idx[fut]
                try:
                    results[k] = fut.result()
                except Exception as e:
                    logger.error(f"LLM judge failed for pair {k}: {e}")
                    results[k] = candidate_pairs[k][2] >= 0.92
                done += 1
                if progress and done % 5 == 0:
                    pct = 30 + int(50 * done / n_pairs)
                    progress.update(
                        current=pct,
                        message=f"LLM 判等 {done}/{n_pairs}",
                    )

        for k, (idx_a, idx_b, _) in enumerate(candidate_pairs):
            if results.get(k):
                union(idx_a, idx_b)

        groups: Dict[int, List[int]] = {}
        for i in range(len(points)):
            root = find(i)
            groups.setdefault(root, []).append(i)

        return [g for g in groups.values() if len(g) > 1]

    def _llm_judge_equivalence(
        self,
        point_a: KnowledgePoint,
        point_b: KnowledgePoint,
        similarity: float,
    ) -> bool:
        """LLM 判断两个知识点是否等价"""
        if not self.client.available:
            return similarity >= 0.92

        try:
            knowledge_a = {
                "textbook_name": point_a.textbook_name,
                "chapter_title": point_a.chapter_title,
                "name": point_a.name,
                "aliases": point_a.aliases,
                "definition": point_a.definition,
                "category": point_a.category.value,
            }
            knowledge_b = {
                "textbook_name": point_b.textbook_name,
                "chapter_title": point_b.chapter_title,
                "name": point_b.name,
                "aliases": point_b.aliases,
                "definition": point_b.definition,
                "category": point_b.category.value,
            }

            system_prompt, user_prompt = build_alignment_prompt(
                knowledge_a, knowledge_b, similarity
            )

            response_text, _ = self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=512,
            )
            data = self._parse_json_response(response_text)
            judgment = data.get("judgment", "DIFFERENT")
            confidence = float(data.get("confidence", 0.0))

            return judgment == "EQUIVALENT" and confidence >= 0.7

        except Exception as e:
            logger.error(f"LLM alignment failed: {e}")
            return similarity >= 0.92

    def _parse_json_response(self, response_text: str) -> dict:
        """解析 LLM 响应中的 JSON"""
        json_block_match = re.search(
            r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL
        )
        if json_block_match:
            json_str = json_block_match.group(1)
        else:
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                json_str = response_text[start : end + 1]
            else:
                json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}

    def _make_decisions(
        self,
        points: List[KnowledgePoint],
        equivalent_groups: List[List[int]],
        denominator_words: int,
        target_ratio: float,
    ) -> List[IntegrationAction]:
        """基于等价组生成整合决策

        策略：
        1. 等价组 → MERGE 决策
        2. 单独节点 → KEEP 决策
        3. 如果压缩比超出目标，对低重要性节点执行 REMOVE
        """
        decisions = []
        merged_indices = set()

        for group in equivalent_groups:
            primary_idx = max(
                group, key=lambda i: (points[i].frequency, len(points[i].definition))
            )
            secondary_indices = [i for i in group if i != primary_idx]

            decision = IntegrationAction(
                action_id=str(uuid.uuid4()),
                decision=IntegrationDecision.MERGE,
                primary_knowledge_id=points[primary_idx].knowledge_id,
                secondary_knowledge_ids=[
                    points[i].knowledge_id for i in secondary_indices
                ],
                reason=(
                    f"在 {len(group)} 本教材中描述了相同概念，"
                    f"合并以减少冗余（保留主版本：{points[primary_idx].textbook_name}）"
                ),
            )
            decisions.append(decision)
            merged_indices.update(group)

        for i, point in enumerate(points):
            if i not in merged_indices:
                decision = IntegrationAction(
                    action_id=str(uuid.uuid4()),
                    decision=IntegrationDecision.KEEP,
                    primary_knowledge_id=point.knowledge_id,
                    secondary_knowledge_ids=[],
                    reason="独有知识点，直接保留",
                )
                decisions.append(decision)

        decisions = self._enforce_compression_ratio(
            decisions, points, denominator_words, target_ratio
        )

        return decisions

    def _enforce_compression_ratio(
        self,
        decisions: List[IntegrationAction],
        points: List[KnowledgePoint],
        denominator_words: int,
        target_ratio: float,
    ) -> List[IntegrationAction]:
        """强制压缩比 ≤ 目标值

        分两轮：
        1. 优先删除 example/application（低教学价值）
        2. 仍超标 → 按重要性升序删除其他类别（保护 theorem/definition + 高频节点）
        """
        id_to_point = {p.knowledge_id: p for p in points}

        if denominator_words <= 0:
            logger.warning("denominator_words is 0 — skipping compression enforcement")
            return decisions

        def kept_words():
            return sum(
                id_to_point[d.primary_knowledge_id].word_count
                for d in decisions
                if d.decision != IntegrationDecision.REMOVE
                and d.primary_knowledge_id in id_to_point
            )

        target_words = int(denominator_words * target_ratio)
        current_words = kept_words()

        if current_words <= target_words:
            logger.info(
                f"Compression target met without removal: "
                f"{current_words}/{denominator_words} = "
                f"{current_words/denominator_words:.2%} ≤ {target_ratio:.2%}"
            )
            return decisions

        excess_words = current_words - target_words
        logger.info(
            f"Need to remove {excess_words} more words to reach {target_ratio:.2%}"
        )

        def importance_score(decision):
            point = id_to_point.get(decision.primary_knowledge_id)
            if not point:
                return 0
            score = point.frequency * 100
            cat = point.category.value
            if cat in ("theorem", "definition"):
                score += 50
            elif cat == "method":
                score += 30
            elif cat == "concept":
                score += 10
            return score

        keep_decisions = sorted(
            [d for d in decisions if d.decision == IntegrationDecision.KEEP],
            key=importance_score,
        )

        words_removed = 0

        # Pass 1: example / application
        for decision in keep_decisions:
            if words_removed >= excess_words:
                break
            point = id_to_point.get(decision.primary_knowledge_id)
            if point and point.category.value in ("example", "application"):
                decision.decision = IntegrationDecision.REMOVE
                decision.reason = "为达到目标压缩比，删除冗余的示例/应用类知识点"
                words_removed += point.word_count

        # Pass 2: low-importance other categories（保护 theorem/definition）
        if words_removed < excess_words:
            for decision in keep_decisions:
                if words_removed >= excess_words:
                    break
                if decision.decision != IntegrationDecision.KEEP:
                    continue
                point = id_to_point.get(decision.primary_knowledge_id)
                if not point:
                    continue
                if point.category.value in ("theorem", "definition"):
                    continue
                if point.frequency >= 2:
                    continue
                decision.decision = IntegrationDecision.REMOVE
                decision.reason = (
                    f"为达到目标压缩比 {target_ratio:.0%}，"
                    f"删除低频低重要性节点（{point.category.value}, freq={point.frequency}）"
                )
                words_removed += point.word_count

        logger.info(
            f"Removed {words_removed} words; final kept = {kept_words()} / "
            f"{denominator_words} = {kept_words()/denominator_words:.2%}"
        )

        return decisions

    def _build_integrated_graph(
        self,
        points: List[KnowledgePoint],
        decisions: List[IntegrationAction],
        original_graphs: List[KnowledgeGraph],
    ) -> KnowledgeGraph:
        """根据整合决策构建合并后的知识图谱"""
        id_to_point = {p.knowledge_id: p for p in points}
        id_mapping = {}
        kept_point_ids = set()

        for decision in decisions:
            if decision.decision == IntegrationDecision.MERGE:
                primary_id = decision.primary_knowledge_id
                kept_point_ids.add(primary_id)
                id_mapping[primary_id] = primary_id

                primary = id_to_point.get(primary_id)
                if primary:
                    for secondary_id in decision.secondary_knowledge_ids:
                        secondary = id_to_point.get(secondary_id)
                        if secondary:
                            primary.aliases = list(
                                set(primary.aliases + [secondary.name] + secondary.aliases)
                            )
                            primary.frequency += secondary.frequency
                        id_mapping[secondary_id] = primary_id

            elif decision.decision == IntegrationDecision.KEEP:
                primary_id = decision.primary_knowledge_id
                kept_point_ids.add(primary_id)
                id_mapping[primary_id] = primary_id

        integrated_nodes = [
            id_to_point[pid] for pid in kept_point_ids if pid in id_to_point
        ]

        all_relations = []
        for graph in original_graphs:
            all_relations.extend(graph.edges)

        seen_edges = set()
        integrated_edges = []
        for rel in all_relations:
            new_source = id_mapping.get(rel.source_id)
            new_target = id_mapping.get(rel.target_id)
            if not new_source or not new_target or new_source == new_target:
                continue
            if new_source not in kept_point_ids or new_target not in kept_point_ids:
                continue
            edge_key = (new_source, new_target, rel.relation_type)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            new_rel = KnowledgeRelation(
                relation_id=str(uuid.uuid4()),
                source_id=new_source,
                target_id=new_target,
                relation_type=rel.relation_type,
                description=rel.description,
            )
            integrated_edges.append(new_rel)

        statistics = {
            "total_nodes": len(integrated_nodes),
            "total_edges": len(integrated_edges),
            "merged_count": sum(
                1 for d in decisions if d.decision == IntegrationDecision.MERGE
            ),
            "kept_count": sum(
                1 for d in decisions if d.decision == IntegrationDecision.KEEP
            ),
            "removed_count": sum(
                1 for d in decisions if d.decision == IntegrationDecision.REMOVE
            ),
        }

        return KnowledgeGraph(
            graph_id=str(uuid.uuid4()),
            textbook_id=None,
            is_integrated=True,
            nodes=integrated_nodes,
            edges=integrated_edges,
            statistics=statistics,
        )


graph_alignment = GraphAlignment()
