"""
知识图谱 API
"""
import logging

from fastapi import APIRouter, HTTPException

from api.store import store
from modules.graph_builder import graph_builder


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/build/{textbook_id}")
async def build_graph(textbook_id: str):
    """为指定教材构建知识图谱"""
    textbook = store.get_textbook(textbook_id)
    if not textbook:
        raise HTTPException(status_code=404, detail="Textbook not found")

    existing = store.get_graph_by_textbook(textbook_id)
    if existing:
        return {
            "graph_id": existing.graph_id,
            "message": "Graph already exists",
            "data": graph_builder.to_cytoscape_format(existing),
        }

    try:
        graph = graph_builder.build_from_textbook(textbook)
        store.add_graph(graph)
        return {
            "graph_id": graph.graph_id,
            "message": f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges",
            "data": graph_builder.to_cytoscape_format(graph),
        }
    except Exception as e:
        logger.error(f"Failed to build graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {str(e)}")


@router.get("/textbook/{textbook_id}")
async def get_graph_by_textbook(textbook_id: str):
    """获取教材的知识图谱"""
    graph = store.get_graph_by_textbook(textbook_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    return {
        "graph_id": graph.graph_id,
        "data": graph_builder.to_cytoscape_format(graph),
    }


@router.get("/{graph_id}")
async def get_graph(graph_id: str):
    """获取指定图谱"""
    graph = store.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    return {
        "graph_id": graph.graph_id,
        "data": graph_builder.to_cytoscape_format(graph),
    }
