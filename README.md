# 学科知识整合智能体

一个基于 AI 的学科知识整合系统，能够对多本教材进行知识整合、去重提纯、构建可视化知识图谱、并基于整合后的知识库进行精准 RAG 问答。

## 🎯 项目目标

- 自动加载多本教材（支持 PDF、DOCX、Markdown、TXT 等多种格式）
- 为每本教材构建知识图谱并可视化展示
- 跨教材识别知识点的重叠、互补与缺失
- 将多本教材的内容整合压缩到不超过原始体量 30% 的精华版本
- 基于整合后的知识库进行 RAG 精准问答（必须引用原文来源）
- 支持教师通过多轮对话迭代优化整合方案

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Web 前端（Vue 3）                          │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ 教材管理  │ 知识图谱  │ 整合操作  │RAG问答   │多轮对话  │   │
│  │ 区域     │ 可视化   │ 面板     │ 面板     │ 面板     │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓ REST API
┌─────────────────────────────────────────────────────────────┐
│                  后端服务（FastAPI）                          │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ 文件解析  │ 知识提取  │ 图谱整合  │RAG管道   │Agent协调 │   │
│  │ 模块     │ 模块     │ 模块     │ 模块     │ 模块     │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                 │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │PostgreSQL│ FAISS    │ Neo4j    │ Redis    │              │
│  │(元数据)  │(向量索引)│(知识图谱)│(缓存)    │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## 📋 核心功能

### P0 基础功能（必须实现）

1. **多格式教材加载与解析** - 支持 PDF、DOCX、Markdown、TXT 等格式
2. **单本教材知识图谱构建** - 自动提取知识点并识别关系
3. **知识图谱交互** - 支持点击、缩放、拖拽、搜索等交互
4. **跨教材知识整合** - 识别重复知识点，执行整合决策，控制压缩比 ≤30%
5. **RAG 精准问答** - 完整 pipeline：分块→embedding→检索→生成+引用
6. **Agent 架构设计** - 提交详细的架构说明文档
7. **多轮对话迭代** - 教师可通过对话修改整合决策
8. **Web 交互界面** - 单页应用，所有功能在浏览器中可用
9. **整合报告** - 输出完整的整合报告
10. **开发文档** - 完整的文档和部署说明

### P1 加分项

- 知识图谱多视图切换
- 混合检索（向量 + BM25）+ Rerank
- Token 消耗统计与可视化
- 支持本地部署开源模型
- Docker 一键部署
- 自建 RAG Benchmark

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Neo4j 5+（可选）

### 安装步骤

#### 1. 克隆仓库并进入项目目录

```bash
git clone <repository-url>
cd knowledge-integration-agent
```

#### 2. 配置环境变量

```bash
# 复制环境变量示例文件到项目根目录
cp src/backend/.env.example .env

# 编辑 .env 文件，填入你的配置
# 必需配置：
# - PROVIDER_BASE_URL: OpenAI 兼容 LLM 端点（如 https://v2.pincc.ai 或 https://api.openai.com）
# - PROVIDER_AUTH_TOKEN: API Token（sk-xxxxxx）
# - MODEL_NAME: 模型名称（默认 claude-haiku-4-5-20251001）
# - DATABASE_URL: PostgreSQL 连接字符串（生产环境）
# - REDIS_URL: Redis 连接字符串（生产环境）
```

#### 3. 安装 Python 依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # 在 Windows 上使用 venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### 4. 安装前端依赖

```bash
cd src/frontend
npm install
cd ../..
```

#### 5. 启动开发服务器

```bash
# 方式 1：使用 Docker Compose（推荐）
docker-compose -f docker-compose.dev.yml up

# 方式 2：手动启动后端和前端
# 终端 1：启动后端
cd src/backend
python main.py

# 终端 2：启动前端
cd src/frontend
npm run dev
```

#### 6. 访问应用

打开浏览器访问 `http://localhost:3000`

## 📖 使用说明

### 1. 上传教材

1. 在左侧"教材管理"区域点击"上传教材"
2. 选择或拖拽教材文件（支持 PDF、DOCX、MD、TXT）
3. 系统自动解析教材并提取章节结构

### 2. 构建知识图谱

1. 上传教材后，系统自动为每本教材构建知识图谱
2. 在中间区域可视化展示知识图谱
3. 点击节点查看详细信息（定义、所在章节、页码等）

### 3. 整合多本教材

1. 上传 2 本或以上教材
2. 点击"开始整合"按钮
3. 系统自动识别重复知识点并输出整合决策
4. 查看压缩比统计和整合前后的对比

### 4. RAG 问答

1. 在右侧"RAG 问答"面板输入问题
2. 系统基于整合后的知识库进行检索和生成
3. 查看回答和来源引用（教材名、章节、页码）

### 5. 多轮对话迭代

1. 在"多轮对话"面板与系统进行对话
2. 可以修改整合决策（如"不应该合并这两个知识点"）
3. 系统实时更新知识图谱并反馈结果

## 📁 项目结构

```
knowledge-integration-agent/
├── README.md                          # 项目说明
├── .gitignore                         # Git 配置
├── requirements.txt                   # Python 依赖
├── package.json                       # 前端依赖
├── docker-compose.yml                 # 生产部署
├── docker-compose.dev.yml             # 开发部署
│
├── docs/
│   ├── 需求分析.md                    # 问题分解与子问题分析
│   ├── 系统设计.md                    # 架构设计、数据流、技术选型
│   ├── Agent架构说明.md               # Agent 架构设计决策与论证
│   ├── 接口文档.md                    # API 接口定义
│   └── RAG_Benchmark.md               # RAG 评测集与优化对比
│
├── src/
│   ├── backend/
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── config.py                  # 配置管理
│   │   ├── .env.example               # 环境变量示例
│   │   ├── modules/                   # 核心模块
│   │   ├── api/                       # API 路由
│   │   ├── models/                    # 数据模型
│   │   ├── db/                        # 数据库连接
│   │   └── prompts/                   # LLM Prompt 模板
│   │
│   └── frontend/
│       ├── index.html                 # 主页面
│       ├── main.js                    # 应用入口
│       ├── components/                # Vue 组件
│       ├── services/                  # API 服务
│       └── assets/                    # 静态资源
│
├── report/
│   └── 整合报告.md                    # 整合报告示例
│
└── tests/
    ├── test_file_parser.py            # 文件解析测试
    ├── test_knowledge_extractor.py    # 知识提取测试
    └── ...                            # 其他测试
```

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|-----|------|------|
| 后端框架 | FastAPI | 异步支持、自动文档、性能优秀 |
| 前端框架 | Vue 3 | 学习曲线平缓、生态完整 |
| 可视化 | Cytoscape.js | 功能最强、交互丰富 |
| 文件解析 | PyMuPDF + python-docx | 支持多格式 |
| 向量嵌入 | BGE-small-zh | 中文支持好、本地运行 |
| 向量检索 | FAISS | 轻量级、快速 |
| 知识图谱 | Neo4j | 图数据库标准 |
| 元数据存储 | PostgreSQL | 可靠、生产就绪 |
| 缓存 | Redis | 高性能 |
| 大模型 | OpenAI 兼容（默认 claude-haiku-4-5） | 通过 pincc.ai/官方 OpenAI/vLLM 等代理调用，灵活切换 |

## 📊 API 接口

### 教材管理

```
POST   /api/textbooks/upload          # 上传教材
GET    /api/textbooks                 # 获取教材列表
GET    /api/textbooks/{id}            # 获取教材详情
DELETE /api/textbooks/{id}            # 删除教材
```

### 知识图谱

```
POST   /api/graphs/build/{textbook_id}      # 构建教材知识图谱（已存在则复用）
GET    /api/graphs/textbook/{textbook_id}   # 按教材获取图谱
GET    /api/graphs/{graph_id}               # 按图谱ID获取图谱
```

### RAG 问答

```
POST   /api/rag/index                 # 建立向量索引
POST   /api/rag/query                 # 提问并获得回答
GET    /api/rag/status                # 查询索引状态
```

### 多轮对话

```
POST   /api/dialogue/chat             # 发送对话消息
GET    /api/dialogue/history          # 获取对话历史
```

详见 `docs/接口文档.md`

## 📈 性能指标

- 文件解析：< 10 秒（单本 500 页 PDF）
- 知识提取：< 30 秒（单章节）
- 知识图谱构建：< 1 分钟（单本教材）
- 跨教材整合：< 5 分钟（7 本教材）
- RAG 检索：< 2 秒（top-5）
- 生成回答：< 5 秒（平均）

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_file_parser.py

# 运行测试并生成覆盖率报告
pytest --cov=src/backend tests/
```

## 📝 文档

- [需求分析](docs/需求分析.md) - 问题分解与子问题分析
- [系统设计](docs/系统设计.md) - 架构设计、数据流、技术选型
- [Agent 架构说明](docs/Agent架构说明.md) - 架构设计决策与论证
- [接口文档](docs/接口文档.md) - API 接口定义
- [RAG Benchmark](docs/RAG_Benchmark.md) - 评测集与优化对比

## 🚀 部署

### Docker 部署（推荐）

```bash
# 生产环境部署
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 手动部署

详见 [部署指南](docs/部署指南.md)

## 📄 许可证

MIT License

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件至 [your-email@example.com]

## ✅ 当前优化版本（2026-05）

- 图谱渲染升级为更稳健的力导向布局（cose-bilkent），节点/关系标签可读性显著提升。
- 关系标签支持中英双行展示（英文在上，中文在下），并补全 `depends_on` 中文映射。
- 图谱交互支持关系线聚焦避让（突出选中关系，弱化非相关元素），便于密集区域阅读。
- 整合任务结果载荷瘦身：任务状态不再携带大图对象，改为轻量指标与结果 ID。
- 内存治理优化：任务存储增加 TTL 与数量上限，整合结果保留最近 N 条，RAG 索引去重与上限控制。
- 教材图谱切换稳定性修复：增加请求并发保护与图谱实例重建版本号，连续切换教材更稳定。

---

**最后更新**：2026-05-15
