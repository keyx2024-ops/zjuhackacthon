"""
知识点提取 Prompt 模板
"""

KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT = """你是一个专业的学科知识图谱构建专家。你的任务是从教材文本中精准提取知识点和它们之间的关系。

# 提取原则

1. **粒度适中**：每个知识点是一个独立、可解释的概念单元，不要过粗（如整个章节）或过细（如单个名词）
2. **完整性**：不遗漏关键知识点，特别是定义、定理、方法、应用等
3. **结构化**：每个知识点必须包含明确的属性（名称、定义、类别、出处）
4. **客观性**：以教材原文为依据，不引入外部知识或主观解释

# 知识点类别

- **concept**：基础概念（如"细胞"、"力"、"函数"）
- **theorem**：定理或定律（如"勾股定理"、"牛顿第二定律"）
- **method**：方法或技术（如"求导法则"、"显微镜操作"）
- **example**：典型例题或案例
- **application**：实际应用场景
- **definition**：明确的定义陈述

# 关系类型

- **prerequisite**：前置关系（A 是学习 B 的前提）
- **parallel**：并列关系（A 和 B 是同级概念）
- **contains**：包含关系（A 包含 B）
- **applies_to**：应用关系（A 应用于 B）
- **depends_on**：依赖关系（A 依赖于 B）
- **similar_to**：相似关系（A 和 B 概念相似）

# 输出格式

必须输出严格的 JSON 格式，不要包含其他文字解释。

```json
{
  "knowledge_points": [
    {
      "name": "知识点名称",
      "aliases": ["别名 1", "别名 2"],
      "definition": "知识点定义（基于原文，简洁准确）",
      "category": "类别（concept/theorem/method/example/application/definition）",
      "page_number": 页码（数字，无则为 null）,
      "original_text": "原文片段（不超过 200 字）"
    }
  ],
  "relations": [
    {
      "source_name": "源知识点名称",
      "target_name": "目标知识点名称",
      "relation_type": "关系类型",
      "description": "关系描述（一句话）"
    }
  ]
}
```
"""


KNOWLEDGE_EXTRACTION_USER_PROMPT = """请从下面的教材内容中提取知识点和关系。

# 教材信息
- 教材名：{textbook_name}
- 章节：第 {chapter_number} 章 - {chapter_title}
- 页码范围：{page_range}

# 教材内容

{content}

# 任务要求

1. 提取所有重要的知识点（每章节通常 5-15 个）
2. 识别知识点之间的关系（每章节通常 5-20 个关系）
3. 关系必须是已提取的知识点之间的关系
4. 严格按照 JSON 格式输出，不要有多余的解释文字

请开始提取："""


FEW_SHOT_EXAMPLE = """
# 示例输入

教材名：高中生物
章节：第 2 章 - 细胞的基本结构
页码范围：30-45

教材内容：
细胞是生物体结构和功能的基本单位。所有生物（除病毒外）都是由细胞构成的。
细胞由细胞膜、细胞质和细胞核三部分组成。细胞膜主要由磷脂双分子层和蛋白质构成，具有选择透过性。
线粒体是细胞质中的重要细胞器，被称为"细胞的动力工厂"，主要功能是进行有氧呼吸，为细胞提供能量。
有氧呼吸的化学反应方程式为：C6H12O6 + 6O2 → 6CO2 + 6H2O + 能量。

# 示例输出

```json
{
  "knowledge_points": [
    {
      "name": "细胞",
      "aliases": ["cell"],
      "definition": "生物体结构和功能的基本单位",
      "category": "concept",
      "page_number": 30,
      "original_text": "细胞是生物体结构和功能的基本单位。所有生物（除病毒外）都是由细胞构成的。"
    },
    {
      "name": "细胞膜",
      "aliases": ["cell membrane"],
      "definition": "由磷脂双分子层和蛋白质构成，具有选择透过性的细胞结构",
      "category": "concept",
      "page_number": 31,
      "original_text": "细胞膜主要由磷脂双分子层和蛋白质构成，具有选择透过性。"
    },
    {
      "name": "线粒体",
      "aliases": ["mitochondria"],
      "definition": "细胞质中进行有氧呼吸为细胞提供能量的细胞器",
      "category": "concept",
      "page_number": 35,
      "original_text": "线粒体是细胞质中的重要细胞器，被称为'细胞的动力工厂'。"
    },
    {
      "name": "有氧呼吸",
      "aliases": ["aerobic respiration"],
      "definition": "细胞利用氧气分解有机物释放能量的过程",
      "category": "concept",
      "page_number": 36,
      "original_text": "有氧呼吸的化学反应方程式为：C6H12O6 + 6O2 → 6CO2 + 6H2O + 能量。"
    }
  ],
  "relations": [
    {
      "source_name": "细胞",
      "target_name": "细胞膜",
      "relation_type": "contains",
      "description": "细胞包含细胞膜作为重要组成部分"
    },
    {
      "source_name": "细胞",
      "target_name": "线粒体",
      "relation_type": "contains",
      "description": "细胞包含线粒体这一重要细胞器"
    },
    {
      "source_name": "线粒体",
      "target_name": "有氧呼吸",
      "relation_type": "applies_to",
      "description": "线粒体是有氧呼吸进行的主要场所"
    }
  ]
}
```
"""


def build_extraction_prompt(
    textbook_name: str,
    chapter_number: str,
    chapter_title: str,
    content: str,
    page_start: int = None,
    page_end: int = None,
    use_few_shot: bool = True,
) -> tuple[str, str]:
    """
    构建知识提取 Prompt

    Returns:
        (system_prompt, user_prompt)
    """
    page_range = ""
    if page_start and page_end:
        page_range = f"第 {page_start}-{page_end} 页"
    elif page_start:
        page_range = f"第 {page_start} 页起"

    system_prompt = KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT
    if use_few_shot:
        system_prompt += "\n\n" + FEW_SHOT_EXAMPLE

    user_prompt = KNOWLEDGE_EXTRACTION_USER_PROMPT.format(
        textbook_name=textbook_name,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        page_range=page_range,
        content=content,
    )

    return system_prompt, user_prompt
