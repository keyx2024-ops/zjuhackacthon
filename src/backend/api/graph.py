"""
知识图谱 API
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

from api.jobs import job_store
from api.store import store
from modules.graph_builder import graph_builder


logger = logging.getLogger(__name__)
router = APIRouter()


def _graph_response(graph, *, message: str, build_status: str) -> dict:
    return {
        "graph_id": graph.graph_id,
        "message": message,
        "build_status": build_status,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "data": graph_builder.to_cytoscape_format(graph),
    }


def start_graph_build_job(textbook_id: str, *, force: bool = False) -> dict:
    textbook = store.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=404, detail="Textbook not found")

    existing = store.get_graph_by_textbook(textbook_id)
    if existing and not force:
        return {
            "status": "completed",
            "result": _graph_response(existing, message="Graph already exists", build_status="cached"),
        }

    handle = job_store.create()
    handle.update(
        phase="准备构建教材图谱",
        current=0,
        total=max(len(textbook.chapters), 1),
        message=textbook.name,
    )
    asyncio.create_task(_run_graph_build(handle, textbook_id, force))
    return {"job_id": handle.job_id, "status": "running"}


@router.post("/build/{textbook_id}")
async def build_graph(textbook_id: str, force: bool = Query(default=False)):
    """为指定教材构建知识图谱"""
    return start_graph_build_job(textbook_id, force=force)


@router.get("/progress/{job_id}")
async def get_graph_build_progress(job_id: str):
    state = job_store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state.to_dict()


async def _run_graph_build(handle, textbook_id: str, force: bool) -> None:
    textbook = store.get_textbook(textbook_id)
    if not textbook:
        job_store.fail(handle.job_id, "Textbook not found")
        return

    try:
        graph = await asyncio.to_thread(
            graph_builder.build_from_textbook, textbook, handle
        )
        store.add_graph(graph)
        result = _graph_response(
            graph,
            message=f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges",
            build_status="built",
        )
        job_store.complete(handle.job_id, result)
    except Exception as e:
        logger.error(f"Failed to build graph: {e}", exc_info=True)
        job_store.fail(handle.job_id, f"Failed to build graph: {str(e)}")


@router.get("/textbook/{textbook_id}")
async def get_graph_by_textbook(textbook_id: str):
    """获取教材的知识图谱"""
    graph = store.get_graph_by_textbook(textbook_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    return _graph_response(graph, message="Loaded existing graph", build_status="cached")


@router.get("/{graph_id}")
async def get_graph(graph_id: str):
    """获取指定图谱"""
    graph = store.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    return _graph_response(graph, message="Loaded existing graph", build_status="cached")
