"""
RAG 管道模块

完整 pipeline：
1. 文档分块（500-800 字，50-100 字重叠）
2. 向量嵌入（BGE-small-zh）
3. 混合检索（向量 + BM25）
4. Rerank 重排
5. LLM 生成 + 引用
"""
import logging
import re
import time
import uuid
from collections import Counter
from typing import List, Optional, Set, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings
from models.rag import Citation, DocumentChunk, IndexStatus, RAGQuery, RAGResponse
from models.textbook import Textbook
from modules.llm_client import llm_client
from prompts.rag_generation import build_rag_prompt


logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG 检索增强生成管道"""

    def __init__(self):
        self.embedding_model = None
        self.client = llm_client
        self.chunks: List[DocumentChunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self.token_to_chunks: dict = {}
        self.indexed_textbook_ids: Set[str] = set()
        self.max_chunks = 20000

    def _get_embedding_model(self):
        """懒加载 embedding 模型"""
        if self.embedding_model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self.embedding_model = SentenceTransformer(
                settings.embedding_model, device=settings.embedding_device
            )
        return self.embedding_model

    def index_textbook(self, textbook: Textbook) -> int:
        """
        为教材建立向量索引

        Args:
            textbook: 教材对象

        Returns:
            生成的分块数量
        """
        logger.info(f"Indexing textbook: {textbook.name}")

        if textbook.textbook_id in self.indexed_textbook_ids:
            logger.info(f"Textbook already indexed, skip: {textbook.textbook_id}")
            return 0

        new_chunks = []
        for chapter in textbook.chapters:
            chapter_chunks = self._chunk_text(
                content=chapter.content,
                textbook_id=textbook.textbook_id,
                textbook_name=textbook.name,
                chapter_id=chapter.chapter_id,
                chapter_title=chapter.title,
                page_start=chapter.page_start,
            )
            new_chunks.extend(chapter_chunks)

        logger.info(f"Generated {len(new_chunks)} chunks for {textbook.name}")

        if len(self.chunks) + len(new_chunks) > self.max_chunks:
            raise ValueError(
                f"RAG index chunk limit exceeded: {len(self.chunks) + len(new_chunks)} > {self.max_chunks}"
            )

        model = self._get_embedding_model()
        texts = [chunk.content for chunk in new_chunks]
        new_embeddings = model.encode(
            texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        )

        self.chunks.extend(new_chunks)
        if self.embeddings is None:
            self.embeddings = np.array(new_embeddings)
        else:
            self.embeddings = np.vstack([self.embeddings, np.array(new_embeddings)])

        self._build_inverted_index(new_chunks)
        self.indexed_textbook_ids.add(textbook.textbook_id)

        logger.info(f"Indexed {len(new_chunks)} chunks. Total: {len(self.chunks)}")
        return len(new_chunks)

    def _chunk_text(
        self,
        content: str,
        textbook_id: str,
        textbook_name: str,
        chapter_id: str,
        chapter_title: str,
        page_start: Optional[int] = None,
    ) -> List[DocumentChunk]:
        """
        文档分块

        策略：
        - 优先按段落（双换行）切分
        - 控制每块大小为 chunk_size 字（约 500-800 字）
        - 块之间有 chunk_overlap 字重叠（约 50-100 字）
        """
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap

        paragraphs = [p.strip() for p in re.split(r"\n\n+", content) if p.strip()]

        chunks = []
        current_text = ""
        chunk_index = 0
        overlap_text = ""

        for para in paragraphs:
            if len(current_text) + len(para) > chunk_size and current_text:
                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    content=current_text.strip(),
                    textbook_id=textbook_id,
                    textbook_name=textbook_name,
                    chapter_id=chapter_id,
                    chapter_title=chapter_title,
                    page_number=page_start,
                    chunk_index=chunk_index,
                    word_count=len(current_text),
                )
                chunks.append(chunk)
                chunk_index += 1

                # 计算重叠部分（从当前块的末尾取）
                if overlap > 0 and len(current_text) > overlap:
                    overlap_text = current_text[-overlap:]
                    current_text = overlap_text + "\n\n" + para
                else:
                    overlap_text = ""
                    current_text = para
            else:
                if current_text:
                    current_text += "\n\n" + para
                else:
                    current_text = para

        if current_text.strip():
            chunk = DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                content=current_text.strip(),
                textbook_id=textbook_id,
                textbook_name=textbook_name,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                page_number=page_start,
                chunk_index=chunk_index,
                word_count=len(current_text),
            )
            chunks.append(chunk)

        return chunks

    def _build_inverted_index(self, chunks: List[DocumentChunk]):
        """构建倒排索引（用于 BM25 检索）"""
        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            for token in set(tokens):
                if token not in self.token_to_chunks:
                    self.token_to_chunks[token] = []
                self.token_to_chunks[token].append(chunk.chunk_id)

    def _tokenize(self, text: str) -> List[str]:
        """简易中英文分词"""
        text = text.lower()
        cn_tokens = re.findall(r"[一-鿿]", text)
        en_tokens = re.findall(r"[a-z]+", text)
        return cn_tokens + en_tokens

    def query(self, rag_query: RAGQuery) -> RAGResponse:
        """
        执行 RAG 查询

        Returns:
            RAGResponse: 包含回答、引用、性能指标
        """
        start_time = time.time()

        if not self.chunks:
            return RAGResponse(
                query=rag_query.query,
                answer="索引为空，请先上传并索引教材。",
                citations=[],
                total_time=time.time() - start_time,
            )

        retrieval_start = time.time()
        relevant_chunks = self._retrieve(rag_query)
        retrieval_time = time.time() - retrieval_start

        if rag_query.use_rerank and len(relevant_chunks) > rag_query.top_k:
            relevant_chunks = self._rerank(rag_query.query, relevant_chunks)[
                : rag_query.top_k
            ]
        else:
            relevant_chunks = relevant_chunks[: rag_query.top_k]

        generation_start = time.time()
        answer, token_usage = self._generate(rag_query.query, relevant_chunks)
        generation_time = time.time() - generation_start

        citations = self._build_citations(relevant_chunks, answer)

        total_time = time.time() - start_time
        return RAGResponse(
            query=rag_query.query,
            answer=answer,
            citations=citations,
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=total_time,
            token_usage=token_usage,
        )

    def _retrieve(self, rag_query: RAGQuery) -> List[DocumentChunk]:
        """混合检索（向量 + BM25）"""
        retrieve_count = max(rag_query.top_k * 4, 20)

        vector_results = self._vector_search(rag_query.query, retrieve_count)

        if not rag_query.use_hybrid_search:
            return vector_results

        bm25_results = self._bm25_search(rag_query.query, retrieve_count)
        merged = self._reciprocal_rank_fusion(vector_results, bm25_results)
        return merged[:retrieve_count]

    def _vector_search(self, query: str, top_k: int) -> List[DocumentChunk]:
        """向量检索"""
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        model = self._get_embedding_model()
        query_embedding = model.encode([query], normalize_embeddings=True)[0]

        scores = self.embeddings @ query_embedding
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            chunk_copy = chunk.model_copy()
            chunk_copy.metadata = {
                **chunk_copy.metadata,
                "vector_score": float(scores[idx]),
            }
            results.append(chunk_copy)
        return results

    def _bm25_search(self, query: str, top_k: int) -> List[DocumentChunk]:
        """BM25 关键词检索"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        chunk_scores = Counter()
        for token in query_tokens:
            if token in self.token_to_chunks:
                df = len(self.token_to_chunks[token])
                idf = np.log(len(self.chunks) / (1 + df))
                for chunk_id in self.token_to_chunks[token]:
                    chunk_scores[chunk_id] += idf

        chunk_id_to_chunk = {c.chunk_id: c for c in self.chunks}
        sorted_chunk_ids = chunk_scores.most_common(top_k)

        results = []
        for chunk_id, score in sorted_chunk_ids:
            chunk = chunk_id_to_chunk.get(chunk_id)
            if chunk:
                chunk_copy = chunk.model_copy()
                chunk_copy.metadata = {**chunk_copy.metadata, "bm25_score": score}
                results.append(chunk_copy)
        return results

    def _reciprocal_rank_fusion(
        self,
        list1: List[DocumentChunk],
        list2: List[DocumentChunk],
        k: int = 60,
    ) -> List[DocumentChunk]:
        """RRF 融合两个排序列表"""
        scores = {}
        chunk_map = {}

        for rank, chunk in enumerate(list1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            chunk_map[chunk.chunk_id] = chunk

        for rank, chunk in enumerate(list2):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (k + rank + 1)
            chunk_map[chunk.chunk_id] = chunk

        sorted_chunk_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for chunk_id, score in sorted_chunk_ids:
            chunk = chunk_map[chunk_id]
            chunk.metadata = {**chunk.metadata, "rrf_score": score}
            results.append(chunk)
        return results

    def _rerank(
        self, query: str, chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """
        重排序

        简化实现：基于 query 和 chunk 内容的精细相似度
        生产环境可使用 cross-encoder 模型
        """
        model = self._get_embedding_model()
        query_emb = model.encode([query], normalize_embeddings=True)[0]
        chunk_texts = [c.content[:500] for c in chunks]
        chunk_embs = model.encode(
            chunk_texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False
        )

        scores = chunk_embs @ query_emb
        ranked = sorted(
            zip(chunks, scores), key=lambda x: float(x[1]), reverse=True
        )
        return [chunk for chunk, _ in ranked]

    def _generate(
        self, query: str, chunks: List[DocumentChunk]
    ) -> Tuple[str, dict]:
        """生成回答"""
        if not chunks:
            return "未找到相关内容，无法回答此问题。", {}

        if not self.client.available:
            answer = self._mock_generate(query, chunks)
            return answer, {}

        try:
            system_prompt, user_prompt = build_rag_prompt(query, chunks)
            answer, token_usage = self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2048,
            )
            return answer, token_usage
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._mock_generate(query, chunks), {}

    def _mock_generate(self, query: str, chunks: List[DocumentChunk]) -> str:
        """无 API key 时的 mock 生成"""
        result = f"问题：{query}\n\n基于教材内容：\n\n"
        for i, chunk in enumerate(chunks[:3], start=1):
            snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            result += f"[{i}] {snippet}\n\n"
        result += "\n（mock 模式：未配置 LLM API key）"
        return result

    def _build_citations(
        self, chunks: List[DocumentChunk], answer: str
    ) -> List[Citation]:
        """构建引用列表"""
        citations = []
        cited_chunk_ids = set()

        # 首先收集在回答中被明确引用的块
        for i, chunk in enumerate(chunks, start=1):
            cite_marker = f"[{i}]"
            if cite_marker in answer:
                relevance = chunk.metadata.get(
                    "rrf_score",
                    chunk.metadata.get("vector_score", 0.0),
                )
                citation = Citation(
                    chunk_id=chunk.chunk_id,
                    textbook_name=chunk.textbook_name,
                    chapter_title=chunk.chapter_title,
                    page_number=chunk.page_number,
                    relevance_score=float(relevance),
                    text_snippet=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                )
                citations.append(citation)
                cited_chunk_ids.add(chunk.chunk_id)

        # 如果没有明确引用，添加前 3 个最相关的块
        if not citations and chunks:
            for chunk in chunks[:3]:
                citation = Citation(
                    chunk_id=chunk.chunk_id,
                    textbook_name=chunk.textbook_name,
                    chapter_title=chunk.chapter_title,
                    page_number=chunk.page_number,
                    relevance_score=chunk.metadata.get("rrf_score", chunk.metadata.get("vector_score", 0.0)),
                    text_snippet=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                )
                citations.append(citation)

        return citations

    def get_status(self) -> IndexStatus:
        """获取索引状态"""
        textbook_ids = set(c.textbook_id for c in self.chunks)
        return IndexStatus(
            total_documents=len(textbook_ids),
            total_chunks=len(self.chunks),
            total_textbooks=len(textbook_ids),
            embedding_model=settings.embedding_model,
            index_size=len(self.chunks),
        )


rag_pipeline = RAGPipeline()
