"""
整合操作 API

POST /api/integration/start    -> 立即返回 job_id，后台执行整合
GET  /api/integration/progress/{job_id} -> 进度查询，结束时含 result
GET  /api/integration/latest   -> 最近一次成功的整合结果
GET  /api/integration/{result_id}/decisions -> 决策详情
"""
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.jobs import JobHandle, job_store
from api.store import store
from models.graph import IntegrationDecision
from modules.graph_alignment import graph_alignment
from modules.graph_builder import graph_builder


logger = logging.getLogger(__name__)
router = APIRouter()


class IntegrateRequest(BaseModel):
    textbook_ids: List[str]
    target_ratio: Optional[float] = Field(
        default=None,
        ge=0.01,
        le=1.0,
        description="目标压缩比（0~1）。默认使用配置 target_compression_ratio。",
    )


@router.post("/start")
async def start_integration(request: IntegrateRequest):
    if len(request.textbook_ids) < 2:
        raise HTTPException(
            status_code=400, detail="Integration requires at least 2 textbooks"
        )

    for textbook_id in request.textbook_ids:
        if store.get_textbook(textbook_id) is None:
            raise HTTPException(
                status_code=404, detail=f"Textbook not found: {textbook_id}"
            )

    handle = job_store.create()
    asyncio.create_task(
        _run_integration(handle, request.textbook_ids, request.target_ratio)
    )
    return {"job_id": handle.job_id, "status": "running"}


@router.get("/progress/{job_id}")
async def get_progress(job_id: str):
    state = job_store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state.to_dict()


async def _run_integration(
    handle: JobHandle,
    textbook_ids: List[str],
    target_ratio: Optional[float],
) -> None:
    try:
        graphs = []
        textbook_total_words = 0
        n_books = len(textbook_ids)

        handle.update(phase="构建知识图谱", current=0, total=n_books, message="开始")

        for i, textbook_id in enumerate(textbook_ids):
            textbook = store.get_textbook(textbook_id)
            if textbook is not None:
                textbook_total_words += textbook.total_words

            graph = store.get_graph_by_textbook(textbook_id)
            if graph is None:
                handle.update(
                    phase=f"提取知识点（{i+1}/{n_books} 本教材）",
                    current=i,
                    total=n_books,
                    message=textbook.name if textbook else textbook_id,
                )
                graph = await asyncio.to_thread(
                    graph_builder.build_from_textbook,
                    textbook,
                    handle,
                )
                store.add_graph(graph)
            else:
                handle.update(
                    phase=f"复用已有图谱（{i+1}/{n_books}）",
                    current=i,
                    message=f"已存在 {graph.statistics.get('total_nodes', 0)} 节点",
                )
            graphs.append(graph)
            handle.update(current=i + 1)

        handle.update(phase="跨教材语义对齐", current=0, total=100, message="开始 Embedding")
        result = await asyncio.to_thread(
            graph_alignment.integrate,
            graphs,
            textbook_total_words,
            target_ratio,
            handle,
        )
        store.add_integration_result(result)

        decisions_summary = _summarize_decisions(result.decisions)
        metrics = _build_metrics_payload(result, decisions_summary)

        payload = {
            "result_id": result.result_id,
            "original_total_words": result.original_total_words,
            "integrated_total_words": result.integrated_total_words,
            "compression_ratio": result.compression_ratio,
            "target_ratio": result.target_ratio,
            "original_kp_count": result.original_kp_count,
            "integrated_kp_count": result.integrated_kp_count,
            "decisions_summary": decisions_summary,
            **metrics,
        }
        job_store.complete(handle.job_id, payload)
        logger.info(
            f"[job {handle.job_id}] integration done: "
            f"compression={result.compression_ratio:.2%} "
            f"(target={result.target_ratio:.2%})"
        )
    except Exception as e:
        logger.error(f"[job {handle.job_id}] integration failed: {e}", exc_info=True)
        job_store.fail(handle.job_id, str(e))


@router.get("/latest")
async def get_latest_integration():
    result = store.get_latest_integration()
    if not result:
        raise HTTPException(status_code=404, detail="No integration result available")

    decisions_summary = _summarize_decisions(result.decisions)
    metrics = _build_metrics_payload(result, decisions_summary)

    return {
        "result_id": result.result_id,
        "original_total_words": result.original_total_words,
        "integrated_total_words": result.integrated_total_words,
        "compression_ratio": result.compression_ratio,
        "target_ratio": result.target_ratio,
        "original_kp_count": result.original_kp_count,
        "integrated_kp_count": result.integrated_kp_count,
        "decisions_summary": decisions_summary,
        **metrics,
        "decisions": [d.model_dump() for d in result.decisions],
        "graph_data": graph_builder.to_cytoscape_format(result.integrated_graph),
    }


@router.get("/{result_id}/decisions")
async def get_decisions(result_id: str):
    result = store.get_integration_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Integration result not found")

    return {
        "result_id": result_id,
        "decisions": [d.model_dump() for d in result.decisions],
        "summary": _summarize_decisions(result.decisions),
    }


def _summarize_decisions(decisions: list) -> dict:
    summary = {
        "total": len(decisions),
        "merge_count": 0,
        "keep_count": 0,
        "remove_count": 0,
    }
    for d in decisions:
        if d.decision == IntegrationDecision.MERGE:
            summary["merge_count"] += 1
        elif d.decision == IntegrationDecision.KEEP:
            summary["keep_count"] += 1
        elif d.decision == IntegrationDecision.REMOVE:
            summary["remove_count"] += 1
    return summary


def _build_metrics_payload(result, decisions_summary: dict) -> dict:
    original_words = result.original_total_words or 0
    integrated_words = result.integrated_total_words or 0
    contest_compression_ratio = (
        integrated_words / original_words if original_words > 0 else 0
    )

    merge_count = decisions_summary.get("merge_count", 0)
    keep_count = decisions_summary.get("keep_count", 0)
    remove_count = decisions_summary.get("remove_count", 0)
    total_decisions = decisions_summary.get("total", 0)
    kp_effective = merge_count + keep_count - remove_count
    kp_completeness = (total_decisions / kp_effective) if kp_effective > 0 else 0

    return {
        "contest_compression_ratio": contest_compression_ratio,
        "contest_ratio_numerator": integrated_words,
        "contest_ratio_denominator": original_words,
        "target_ratio": result.target_ratio,
        "target_ratio_met": contest_compression_ratio <= (result.target_ratio or 0),
        "kp_completeness": kp_completeness,
        "kp_ratio_numerator": total_decisions,
        "kp_ratio_denominator": kp_effective,
    }
