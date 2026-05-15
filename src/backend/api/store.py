"""
共享存储

简化实现：内存字典 + JSON 文件持久化。
- 启动时从 data/state.json 加载（如存在）
- 每次 mutation 后原子写盘（temp + rename）
- 写入失败不阻塞 API（只记录 warning）

生产环境应替换为 PostgreSQL + Redis；当前持久化层已足以支撑赛题
要求（重启后教材列表/图谱/整合结果不丢）。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional

from config import PROJECT_ROOT
from models.graph import IntegrationResult, KnowledgeGraph
from models.textbook import Textbook


logger = logging.getLogger(__name__)


STATE_FILE = PROJECT_ROOT / "data" / "state.json"
MAX_INTEGRATION_RESULTS = 10


class InMemoryStore:
    """带 JSON 持久化的内存存储"""

    def __init__(self, state_file: Path = STATE_FILE):
        self.textbooks: Dict[str, Textbook] = {}
        self.graphs: Dict[str, KnowledgeGraph] = {}
        self.graph_by_textbook: Dict[str, str] = {}
        self.integration_results: Dict[str, IntegrationResult] = {}
        self.latest_integration_id: Optional[str] = None

        self._state_file = Path(state_file)
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = json.loads(self._state_file.read_text("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
            return

        for tid, t in (raw.get("textbooks") or {}).items():
            try:
                self.textbooks[tid] = Textbook.model_validate(t)
            except Exception as e:
                logger.warning(f"Skip invalid textbook {tid}: {e}")

        for gid, g in (raw.get("graphs") or {}).items():
            try:
                self.graphs[gid] = KnowledgeGraph.model_validate(g)
            except Exception as e:
                logger.warning(f"Skip invalid graph {gid}: {e}")

        self.graph_by_textbook = dict(raw.get("graph_by_textbook") or {})

        for rid, r in (raw.get("integration_results") or {}).items():
            try:
                self.integration_results[rid] = IntegrationResult.model_validate(r)
            except Exception as e:
                logger.warning(f"Skip invalid integration result {rid}: {e}")

        self.latest_integration_id = raw.get("latest_integration_id")

        logger.info(
            f"Loaded state: {len(self.textbooks)} textbooks, "
            f"{len(self.graphs)} graphs, "
            f"{len(self.integration_results)} integration results"
        )

    def _save(self) -> None:
        try:
            payload = {
                "textbooks": {
                    tid: t.model_dump(mode="json") for tid, t in self.textbooks.items()
                },
                "graphs": {
                    gid: g.model_dump(mode="json") for gid, g in self.graphs.items()
                },
                "graph_by_textbook": self.graph_by_textbook,
                "integration_results": {
                    rid: r.model_dump(mode="json")
                    for rid, r in self.integration_results.items()
                },
                "latest_integration_id": self.latest_integration_id,
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=".state.", suffix=".json", dir=str(self._state_file.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                os.replace(tmp_path, self._state_file)
            except Exception:
                Path(tmp_path).unlink(missing_ok=True)
                raise
        except Exception as e:
            logger.warning(f"Failed to persist state: {e}")

    def add_textbook(self, textbook: Textbook):
        with self._lock:
            self.textbooks[textbook.textbook_id] = textbook
            self._save()

    def get_textbook(self, textbook_id: str) -> Optional[Textbook]:
        return self.textbooks.get(textbook_id)

    def list_textbooks(self) -> list:
        return list(self.textbooks.values())

    def remove_textbook(self, textbook_id: str) -> bool:
        with self._lock:
            if textbook_id in self.textbooks:
                del self.textbooks[textbook_id]
                graph_id = self.graph_by_textbook.pop(textbook_id, None)
                if graph_id and graph_id in self.graphs:
                    del self.graphs[graph_id]
                self._save()
                return True
            return False

    def add_graph(self, graph: KnowledgeGraph):
        with self._lock:
            self.graphs[graph.graph_id] = graph
            if graph.textbook_id:
                self.graph_by_textbook[graph.textbook_id] = graph.graph_id
            self._save()

    def get_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        return self.graphs.get(graph_id)

    def get_graph_by_textbook(self, textbook_id: str) -> Optional[KnowledgeGraph]:
        graph_id = self.graph_by_textbook.get(textbook_id)
        if graph_id:
            return self.graphs.get(graph_id)
        return None

    def add_integration_result(self, result: IntegrationResult):
        with self._lock:
            self.integration_results[result.result_id] = result
            self.latest_integration_id = result.result_id

            if len(self.integration_results) > MAX_INTEGRATION_RESULTS:
                ordered_ids = sorted(
                    self.integration_results.keys(),
                    key=lambda rid: self.integration_results[rid].created_at,
                )
                remove_count = len(self.integration_results) - MAX_INTEGRATION_RESULTS
                for rid in ordered_ids[:remove_count]:
                    if rid != self.latest_integration_id:
                        self.integration_results.pop(rid, None)

            self._save()

    def get_integration_result(self, result_id: str) -> Optional[IntegrationResult]:
        return self.integration_results.get(result_id)

    def get_latest_integration(self) -> Optional[IntegrationResult]:
        if self.latest_integration_id:
            return self.integration_results.get(self.latest_integration_id)
        return None


store = InMemoryStore()
