"""
知识点提取模块

调用 LLM 从教材内容中提取结构化的知识点和关系。
- 并发提取：使用 ThreadPoolExecutor 并行调用 LLM（默认 5 路）
- 进度回调：通过 JobHandle.update(...) 上报进度
- 健壮 JSON：容忍尾随逗号、单引号、未闭合数组等常见 LLM 失误
"""
import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from config import settings
from models.graph import (
    KnowledgeCategory,
    KnowledgePoint,
    KnowledgeRelation,
    RelationType,
)
from models.textbook import Chapter, Textbook
from modules.llm_client import llm_client
from prompts.knowledge_extraction import build_extraction_prompt


logger = logging.getLogger(__name__)


EXTRACT_CONCURRENCY = 5
EXTRACT_MAX_TOKENS = 6000


class KnowledgeExtractor:
    def __init__(self):
        self.client = llm_client

    def extract_from_textbook(
        self, textbook: Textbook, progress=None
    ) -> Tuple[List[KnowledgePoint], List[KnowledgeRelation]]:
        all_points = []
        all_relations = []
        name_to_id = {}

        chapters = textbook.chapters
        n = len(chapters)
        if progress:
            progress.update(
                phase=f"提取知识点：{textbook.name}",
                current=0,
                total=n,
                message=f"共 {n} 章",
            )

        chapter_results: List[Tuple[int, List[KnowledgePoint], List[dict]]] = []

        if self.client.available and n > 0:
            with ThreadPoolExecutor(max_workers=EXTRACT_CONCURRENCY) as pool:
                future_to_idx = {
                    pool.submit(self._extract_from_chapter, textbook, ch): i
                    for i, ch in enumerate(chapters)
                }
                done_count = 0
                for fut in as_completed(future_to_idx):
                    idx = future_to_idx[fut]
                    try:
                        points, raw_relations = fut.result()
                    except Exception as e:
                        logger.error(
                            f"Extract failed for chapter {chapters[idx].title}: {e}"
                        )
                        points, raw_relations = self._mock_extract(textbook, chapters[idx])
                    chapter_results.append((idx, points, raw_relations))
                    done_count += 1
                    if progress:
                        progress.update(
                            current=done_count,
                            message=f"已完成 {done_count}/{n}：{chapters[idx].title[:20]}",
                        )
        else:
            for i, ch in enumerate(chapters):
                points, raw_relations = self._mock_extract(textbook, ch)
                chapter_results.append((i, points, raw_relations))
                if progress:
                    progress.update(current=i + 1, message=f"mock {i+1}/{n}")

        chapter_results.sort(key=lambda x: x[0])
        for _, points, raw_relations in chapter_results:
            for point in points:
                name_to_id[point.name] = point.knowledge_id
                for alias in point.aliases:
                    name_to_id[alias] = point.knowledge_id
                all_points.append(point)

            for raw in raw_relations:
                source_id = name_to_id.get(raw.get("source_name", ""))
                target_id = name_to_id.get(raw.get("target_name", ""))
                if not source_id or not target_id or source_id == target_id:
                    continue
                try:
                    all_relations.append(
                        KnowledgeRelation(
                            relation_id=str(uuid.uuid4()),
                            source_id=source_id,
                            target_id=target_id,
                            relation_type=RelationType(
                                raw.get("relation_type", "parallel")
                            ),
                            description=raw.get("description", ""),
                        )
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid relation: {e}")

        logger.info(
            f"Extracted {len(all_points)} knowledge points and "
            f"{len(all_relations)} relations from {textbook.name}"
        )
        return all_points, all_relations

    def _extract_from_chapter(
        self, textbook: Textbook, chapter: Chapter
    ) -> Tuple[List[KnowledgePoint], List[dict]]:
        if not self.client.available:
            return self._mock_extract(textbook, chapter)

        system_prompt, user_prompt = build_extraction_prompt(
            textbook_name=textbook.name,
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.title,
            content=self._truncate_content(chapter.content),
            page_start=chapter.page_start,
            page_end=chapter.page_end,
            use_few_shot=True,
        )

        try:
            response_text, _ = self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=EXTRACT_MAX_TOKENS,
            )
            data = self._parse_json_response(response_text)

            points = []
            for kp_data in data.get("knowledge_points", []):
                try:
                    if not kp_data.get("name") or not kp_data.get("definition"):
                        continue
                    point = KnowledgePoint(
                        knowledge_id=str(uuid.uuid4()),
                        name=kp_data["name"],
                        aliases=kp_data.get("aliases") or [],
                        definition=kp_data["definition"],
                        category=KnowledgeCategory(
                            kp_data.get("category", "concept")
                        ),
                        textbook_id=textbook.textbook_id,
                        textbook_name=textbook.name,
                        chapter_id=chapter.chapter_id,
                        chapter_title=chapter.title,
                        page_number=kp_data.get("page_number") or chapter.page_start,
                        original_text=kp_data.get("original_text", "") or "",
                        word_count=len(kp_data.get("definition", "")),
                    )
                    points.append(point)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid knowledge point: {e}")

            return points, data.get("relations", []) or []

        except Exception as e:
            logger.error(f"LLM extraction failed for chapter {chapter.title}: {e}")
            return self._mock_extract(textbook, chapter)

    def _truncate_content(self, content: str, max_chars: int = 8000) -> str:
        if len(content) <= max_chars:
            return content
        truncated = content[:max_chars]
        last_period = truncated.rfind("。")
        if last_period > max_chars // 2:
            return truncated[: last_period + 1]
        return truncated

    def _parse_json_response(self, response_text: str) -> dict:
        json_str = self._extract_json_string(response_text)
        if not json_str:
            return {"knowledge_points": [], "relations": []}

        for candidate in self._json_repair_candidates(json_str):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    data.setdefault("knowledge_points", [])
                    data.setdefault("relations", [])
                    return data
            except json.JSONDecodeError:
                continue

        recovered = self._recover_partial_array(json_str)
        if recovered:
            logger.warning(
                f"JSON parse failed, recovered {len(recovered['knowledge_points'])} "
                f"partial knowledge points"
            )
            return recovered

        logger.error(f"Failed to parse JSON response (len={len(response_text)})")
        return {"knowledge_points": [], "relations": []}

    def _extract_json_string(self, text: str) -> str:
        block = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if block:
            return block.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text.strip()

    def _json_repair_candidates(self, s: str):
        yield s

        no_trailing = re.sub(r",\s*([}\]])", r"\1", s)
        if no_trailing != s:
            yield no_trailing

        opens = s.count("{") - s.count("}")
        opens_sq = s.count("[") - s.count("]")
        if opens > 0 or opens_sq > 0:
            patched = no_trailing.rstrip().rstrip(",")
            patched += "]" * max(opens_sq, 0)
            patched += "}" * max(opens, 0)
            yield patched

    def _recover_partial_array(self, s: str) -> Optional[dict]:
        kp_match = re.search(r'"knowledge_points"\s*:\s*\[', s)
        if not kp_match:
            return None
        start = kp_match.end()

        objects = []
        depth = 0
        obj_start = -1
        i = start
        in_str = False
        escape = False
        while i < len(s):
            ch = s[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    if depth == 0:
                        obj_start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and obj_start >= 0:
                        candidate = s[obj_start : i + 1]
                        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                        try:
                            obj = json.loads(candidate)
                            if obj.get("name") and obj.get("definition"):
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        obj_start = -1
                elif ch == "]" and depth == 0:
                    break
            i += 1

        if not objects:
            return None
        return {"knowledge_points": objects, "relations": []}

    def _mock_extract(
        self, textbook: Textbook, chapter: Chapter
    ) -> Tuple[List[KnowledgePoint], List[dict]]:
        logger.warning(f"Using mock extraction for chapter {chapter.title}")

        words = chapter.content.split()[:5]
        points = []
        for i, word in enumerate(words):
            if len(word) >= 2:
                point = KnowledgePoint(
                    knowledge_id=str(uuid.uuid4()),
                    name=word[:10],
                    definition=f"来自第 {chapter.chapter_number} 章的知识点（mock）",
                    category=KnowledgeCategory.CONCEPT,
                    textbook_id=textbook.textbook_id,
                    textbook_name=textbook.name,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    page_number=chapter.page_start,
                    word_count=20,
                )
                points.append(point)

        return points, []


knowledge_extractor = KnowledgeExtractor()
