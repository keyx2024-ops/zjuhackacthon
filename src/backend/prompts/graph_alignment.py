"""
知识图谱对齐 Prompt 模板

用于跨教材知识点的语义对齐和等价判断
"""

GRAPH_ALIGNMENT_SYSTEM_PROMPT = """你是一个专业的学科知识对齐专家。你的任务是判断不同教材中的两个知识点是否描述同一个核心概念。

# 判断原则

1. **核心概念一致**：两个知识点描述的核心概念是否相同（如"白细胞"和"leukocyte"指同一概念）
2. **定义实质相同**：定义的实质内涵是否一致，允许表述方式不同
3. **学科粒度一致**：是否在同一抽象层次（避免"细胞"和"细胞膜"被判定为同一概念）
4. **客观判断**：基于知识点本身，不考虑教材编排差异

# 判断结果

- **EQUIVALENT（等价）**：两个知识点描述完全相同的概念，可以合并
- **RELATED（相关但不等价）**：两个知识点相关但不是同一概念，应保留
- **DIFFERENT（不同）**：两个知识点描述不同概念

# 输出格式

必须输出严格的 JSON 格式：

```json
{
  "judgment": "EQUIVALENT/RELATED/DIFFERENT",
  "confidence": 0.0-1.0,
  "reason": "判断理由（一句话）",
  "merge_suggestion": {
    "preferred_name": "合并后建议的名称（如判断为 EQUIVALENT）",
    "merged_definition": "合并后的定义（综合两个定义的精华）"
  }
}
```
"""


GRAPH_ALIGNMENT_USER_PROMPT = """请判断以下两个知识点是否描述同一个核心概念。

# 知识点 A
- 来源：{textbook_a_name}（第 {chapter_a} 章）
- 名称：{name_a}
- 别名：{aliases_a}
- 定义：{definition_a}
- 类别：{category_a}

# 知识点 B
- 来源：{textbook_b_name}（第 {chapter_b} 章）
- 名称：{name_b}
- 别名：{aliases_b}
- 定义：{definition_b}
- 类别：{category_b}

# Embedding 相似度
{similarity_score}（仅供参考，请基于内容做出独立判断）

请按 JSON 格式输出判断结果："""


INTEGRATION_DECISION_SYSTEM_PROMPT = """你是一个专业的教材整合专家。基于多本教材中的知识点和它们的对齐关系，你需要做出整合决策，将多本教材整合压缩到不超过原始体量 30% 的精华版本，同时保证教学完整性。

# 整合原则

1. **保留必要的知识点**：所有教材都涉及的核心知识点必须保留
2. **合并等价知识点**：不同教材描述同一概念的知识点应合并为一个
3. **删除冗余内容**：相似度高且非核心的内容可删除
4. **保持教学完整性**：不能丢失关键的前置知识或核心定理
5. **平衡压缩比**：目标压缩比 30%，但不应牺牲教学质量

# 决策类型

- **MERGE（合并）**：合并多个等价的知识点为一个
- **KEEP（保留）**：保留某个知识点（无重复或核心知识点）
- **REMOVE（删除）**：删除冗余的非核心知识点

# 输出格式

```json
{
  "decisions": [
    {
      "decision": "MERGE/KEEP/REMOVE",
      "primary_id": "主知识点 ID",
      "secondary_ids": ["次知识点 ID 列表"],
      "reason": "决策理由"
    }
  ],
  "summary": {
    "merge_count": 0,
    "keep_count": 0,
    "remove_count": 0,
    "estimated_compression_ratio": 0.0
  }
}
```
"""


def build_alignment_prompt(
    knowledge_a: dict,
    knowledge_b: dict,
    similarity_score: float,
) -> tuple[str, str]:
    """构建对齐判断 Prompt"""
    user_prompt = GRAPH_ALIGNMENT_USER_PROMPT.format(
        textbook_a_name=knowledge_a.get("textbook_name", ""),
        chapter_a=knowledge_a.get("chapter_title", ""),
        name_a=knowledge_a.get("name", ""),
        aliases_a=", ".join(knowledge_a.get("aliases", [])),
        definition_a=knowledge_a.get("definition", ""),
        category_a=knowledge_a.get("category", ""),
        textbook_b_name=knowledge_b.get("textbook_name", ""),
        chapter_b=knowledge_b.get("chapter_title", ""),
        name_b=knowledge_b.get("name", ""),
        aliases_b=", ".join(knowledge_b.get("aliases", [])),
        definition_b=knowledge_b.get("definition", ""),
        category_b=knowledge_b.get("category", ""),
        similarity_score=f"{similarity_score:.3f}",
    )
    return GRAPH_ALIGNMENT_SYSTEM_PROMPT, user_prompt
