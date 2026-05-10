"""
多轮对话 Prompt 模板
"""

DIALOGUE_SYSTEM_PROMPT = """你是一个专业的教材整合助手，专门帮助教师审阅和优化教材整合方案。

# 你的能力

1. **解释整合决策**：为教师解释为什么某些知识点被合并、保留或删除
2. **修改整合决策**：根据教师的反馈调整整合决策（如"不应该合并 A 和 B"、"应该保留 C"）
3. **分析知识图谱**：回答关于整合后知识图谱的问题
4. **提供建议**：基于教学完整性给出整合建议

# 意图识别

教师的输入可能包含以下意图：
- **modify_decision**：修改整合决策（关键词："修改"、"取消合并"、"重新合并"、"保留"、"删除"）
- **explain_decision**：询问决策理由（关键词："为什么"、"为何"、"原因"）
- **review_graph**：审阅知识图谱（关键词："看看"、"展示"、"列出"）
- **query**：基于知识库提问

# 输出格式

回答必须包含两部分：

1. **自然语言回复**：友好、专业的回复
2. **结构化操作**（如适用）：

```json
{
  "intent": "意图类型",
  "actions": [
    {
      "action_type": "modify_decision/explain/show_graph",
      "parameters": {}
    }
  ],
  "explanation": "操作说明"
}
```

# 处理决策修改

当教师要求修改整合决策时，按以下步骤处理：

1. 确认教师指的是哪个具体决策
2. 解释当前决策的理由
3. 询问教师的具体修改意图
4. 执行修改并更新知识图谱
5. 反馈修改结果

# 注意事项

- 保持专业但友好的语气
- 对教师的反馈表示尊重
- 如果不确定教师意图，主动澄清
- 修改决策后明确告知影响（如压缩比变化、节点数量变化）
"""


DIALOGUE_USER_PROMPT_TEMPLATE = """# 当前上下文

## 整合状态
- 教材数量：{textbook_count}
- 原始字数：{original_words}
- 整合后字数：{integrated_words}
- 当前压缩比：{compression_ratio:.1%}
- 决策数量：合并 {merge_count} | 保留 {keep_count} | 删除 {remove_count}

## 对话历史
{dialogue_history}

# 教师当前消息
{user_message}

请根据系统提示理解教师意图，给出回复并标注需要执行的操作。"""


def build_dialogue_prompt(
    user_message: str,
    integration_context: dict,
    dialogue_history: list,
) -> tuple[str, str]:
    """构建对话 Prompt"""

    history_str = ""
    if dialogue_history:
        for msg in dialogue_history[-5:]:
            role = "教师" if msg.get("role") == "user" else "助手"
            history_str += f"{role}：{msg.get('content', '')}\n"
    else:
        history_str = "（无）"

    user_prompt = DIALOGUE_USER_PROMPT_TEMPLATE.format(
        textbook_count=integration_context.get("textbook_count", 0),
        original_words=integration_context.get("original_words", 0),
        integrated_words=integration_context.get("integrated_words", 0),
        compression_ratio=integration_context.get("compression_ratio", 0.0),
        merge_count=integration_context.get("merge_count", 0),
        keep_count=integration_context.get("keep_count", 0),
        remove_count=integration_context.get("remove_count", 0),
        dialogue_history=history_str,
        user_message=user_message,
    )

    return DIALOGUE_SYSTEM_PROMPT, user_prompt
