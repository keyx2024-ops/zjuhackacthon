"""
多轮对话 Agent 模块

支持教师通过自然语言：
1. 询问整合决策的理由
2. 修改整合决策（取消合并、保留、删除）
3. 查询知识图谱
4. 实时更新知识图谱
"""
import json
import logging
import re
import uuid
from typing import List, Optional

from config import settings
from models.dialogue import (
    DialogueIntent,
    DialogueMessage,
    DialogueRequest,
    DialogueResponse,
    DialogueSession,
    MessageRole,
)
from models.graph import IntegrationDecision, IntegrationResult
from modules.llm_client import llm_client
from prompts.dialogue import build_dialogue_prompt


logger = logging.getLogger(__name__)


class DialogueAgent:
    """多轮对话 Agent"""

    def __init__(self):
        self.client = llm_client
        self.sessions: dict[str, DialogueSession] = {}

    def chat(
        self,
        request: DialogueRequest,
        integration_result: Optional[IntegrationResult] = None,
    ) -> DialogueResponse:
        """
        处理对话请求

        Args:
            request: 对话请求
            integration_result: 当前整合结果（用于上下文）

        Returns:
            DialogueResponse: 对话响应
        """
        session_id = request.session_id or str(uuid.uuid4())
        session = self.sessions.get(session_id)
        if session is None:
            session = DialogueSession(session_id=session_id)
            self.sessions[session_id] = session

        user_message = DialogueMessage(
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=request.message,
        )
        session.messages.append(user_message)

        intent = self._detect_intent(request.message)
        user_message.intent = intent

        integration_context = self._build_context(integration_result)
        history_dicts = [
            {"role": m.role.value, "content": m.content}
            for m in session.messages[-10:-1]
        ]

        if not self.client.available:
            assistant_content = self._mock_response(request.message, intent, integration_context)
            actions = []
        else:
            assistant_content, actions = self._llm_chat(
                request.message, integration_context, history_dicts
            )

        graph_updated = False
        actions_taken = []
        if intent == DialogueIntent.MODIFY_DECISION and integration_result:
            modify_actions = self._apply_decision_modifications(
                request.message, integration_result
            )
            actions_taken.extend(modify_actions)
            graph_updated = len(modify_actions) > 0

        assistant_message = DialogueMessage(
            message_id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            intent=intent,
            metadata={"actions": actions, "graph_updated": graph_updated},
        )
        session.messages.append(assistant_message)

        return DialogueResponse(
            session_id=session_id,
            message=assistant_message,
            actions_taken=actions_taken,
            graph_updated=graph_updated,
        )

    def _detect_intent(self, message: str) -> DialogueIntent:
        """检测用户意图（基于关键词）"""
        message_lower = message.lower()

        modify_keywords = ["修改", "取消合并", "重新合并", "保留", "删除", "不应该", "改成", "调整"]
        explain_keywords = ["为什么", "为何", "原因", "理由", "解释"]
        review_keywords = ["看看", "展示", "列出", "查看", "显示"]

        for kw in modify_keywords:
            if kw in message:
                return DialogueIntent.MODIFY_DECISION

        for kw in explain_keywords:
            if kw in message:
                return DialogueIntent.EXPLAIN_DECISION

        for kw in review_keywords:
            if kw in message:
                return DialogueIntent.REVIEW_GRAPH

        return DialogueIntent.QUERY

    def _build_context(self, integration_result: Optional[IntegrationResult]) -> dict:
        """构建对话上下文"""
        if not integration_result:
            return {
                "textbook_count": 0,
                "original_words": 0,
                "integrated_words": 0,
                "compression_ratio": 0.0,
                "merge_count": 0,
                "keep_count": 0,
                "remove_count": 0,
            }

        merge_count = sum(
            1 for d in integration_result.decisions if d.decision == IntegrationDecision.MERGE
        )
        keep_count = sum(
            1 for d in integration_result.decisions if d.decision == IntegrationDecision.KEEP
        )
        remove_count = sum(
            1 for d in integration_result.decisions if d.decision == IntegrationDecision.REMOVE
        )

        return {
            "textbook_count": len(integration_result.textbook_ids),
            "original_words": integration_result.original_total_words,
            "integrated_words": integration_result.integrated_total_words,
            "compression_ratio": integration_result.compression_ratio,
            "merge_count": merge_count,
            "keep_count": keep_count,
            "remove_count": remove_count,
        }

    def _llm_chat(
        self,
        user_message: str,
        integration_context: dict,
        dialogue_history: list,
    ) -> tuple[str, list]:
        """调用 LLM 处理对话"""
        try:
            system_prompt, user_prompt = build_dialogue_prompt(
                user_message, integration_context, dialogue_history
            )
            response_text, _ = self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2048,
            )
            actions = self._extract_actions(response_text)
            cleaned_text = self._clean_response(response_text)
            return cleaned_text, actions
        except Exception as e:
            logger.error(f"LLM chat failed: {e}")
            return self._mock_response(user_message, DialogueIntent.QUERY, integration_context), []

    def _extract_actions(self, response_text: str) -> list:
        """从响应中提取结构化操作"""
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data.get("actions", [])
            except json.JSONDecodeError:
                pass
        return []

    def _clean_response(self, response_text: str) -> str:
        """从响应中移除 JSON 代码块，保留自然语言部分"""
        cleaned = re.sub(r"```(?:json)?\s*\n.*?\n```", "", response_text, flags=re.DOTALL)
        return cleaned.strip()

    def _apply_decision_modifications(
        self,
        user_message: str,
        integration_result: IntegrationResult,
    ) -> List[str]:
        """应用决策修改"""
        actions = []

        cancel_match = re.search(r"取消合并\s*[：:]?\s*(.+?)(?:和|与)(.+)", user_message)
        if cancel_match:
            name_a = cancel_match.group(1).strip()
            name_b = cancel_match.group(2).strip()
            for decision in integration_result.decisions:
                if decision.decision == IntegrationDecision.MERGE:
                    primary = next(
                        (
                            n
                            for n in integration_result.integrated_graph.nodes
                            if n.knowledge_id == decision.primary_knowledge_id
                        ),
                        None,
                    )
                    if primary and (name_a in primary.name or name_b in primary.name):
                        decision.decision = IntegrationDecision.KEEP
                        decision.is_user_modified = True
                        decision.reason = f"教师反馈：{user_message}"
                        actions.append(f"已取消合并：{primary.name}")
                        break

        keep_match = re.search(r"保留\s*[：:]?\s*(.+?)(?:这个|这一|$)", user_message)
        if keep_match:
            name = keep_match.group(1).strip()
            for decision in integration_result.decisions:
                if decision.decision == IntegrationDecision.REMOVE:
                    primary = next(
                        (
                            n
                            for n in integration_result.integrated_graph.nodes
                            if n.knowledge_id == decision.primary_knowledge_id
                        ),
                        None,
                    )
                    if primary and name in primary.name:
                        decision.decision = IntegrationDecision.KEEP
                        decision.is_user_modified = True
                        decision.reason = f"教师反馈保留：{user_message}"
                        actions.append(f"已保留：{primary.name}")
                        break

        return actions

    def _mock_response(
        self, user_message: str, intent: DialogueIntent, context: dict
    ) -> str:
        """无 API key 时的 mock 回复"""
        if intent == DialogueIntent.EXPLAIN_DECISION:
            return (
                f"当前已对 {context['textbook_count']} 本教材执行整合，"
                f"压缩比为 {context['compression_ratio']:.1%}。"
                f"\n合并 {context['merge_count']} 项、保留 {context['keep_count']} 项、删除 {context['remove_count']} 项。"
                f"\n（mock 模式：未配置 LLM API key）"
            )
        elif intent == DialogueIntent.MODIFY_DECISION:
            return f"已收到您的修改请求：{user_message}\n（mock 模式）"
        elif intent == DialogueIntent.REVIEW_GRAPH:
            return (
                f"当前整合后图谱共有 {context['textbook_count']} 本教材的知识。"
                f"\n详细信息请查看左侧知识图谱可视化区域。"
            )
        else:
            return (
                f"您的问题：{user_message}\n请使用 RAG 问答面板获取更精准的回答。\n（mock 模式）"
            )

    def get_session(self, session_id: str) -> Optional[DialogueSession]:
        """获取对话会话"""
        return self.sessions.get(session_id)


dialogue_agent = DialogueAgent()
