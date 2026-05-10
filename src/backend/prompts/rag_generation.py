"""
RAG 生成 Prompt 模板
"""

RAG_GENERATION_SYSTEM_PROMPT = """你是一个严谨的学科知识问答助手。你的任务是基于提供的教材原文内容，回答用户的问题。

# 回答原则

1. **严格基于原文**：答案必须基于提供的上下文，不要引入外部知识
2. **明确引用**：每个关键信息点必须标注来源 [序号]
3. **逻辑清晰**：回答要结构化、层次分明
4. **坦诚局限**：如果上下文中没有足够信息，明确说明"根据提供的教材内容无法回答"
5. **避免虚构**：绝不编造数字、案例或细节

# 引用格式

在每个关键信息后使用 [序号] 标注来源，序号对应下文上下文中的编号。

# 输出格式

直接给出回答，不要有额外的前缀（如"根据上下文..."）。最后可以用一行附上"参考来源"。

示例：
细胞是生物体结构和功能的基本单位 [1]。细胞主要由细胞膜、细胞质和细胞核组成 [1][2]。其中细胞膜具有选择透过性 [2]。
"""


RAG_GENERATION_USER_PROMPT = """# 用户问题
{query}

# 教材上下文

{context}

# 任务
请基于上述教材内容回答用户问题。每个关键信息点必须标注来源 [序号]。如果上下文中没有足够信息回答，请明确说明。

回答："""


def build_rag_prompt(query: str, chunks: list) -> tuple[str, str]:
    """
    构建 RAG 生成 Prompt

    Args:
        query: 用户问题
        chunks: 检索到的文档块列表

    Returns:
        (system_prompt, user_prompt)
    """
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        source_info = f"[{i}] 来自《{chunk.textbook_name}》 - {chunk.chapter_title}"
        if chunk.page_number:
            source_info += f"（第 {chunk.page_number} 页）"
        context_parts.append(f"{source_info}\n{chunk.content}")

    context = "\n\n---\n\n".join(context_parts)

    user_prompt = RAG_GENERATION_USER_PROMPT.format(query=query, context=context)
    return RAG_GENERATION_SYSTEM_PROMPT, user_prompt
