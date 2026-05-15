<template>
  <div class="rag-container">
    <div class="rag-status">
      <div class="status-item">
        <span class="status-label">已索引教材：</span>
        <span class="status-value">{{ status.total_textbooks || 0 }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">文档块：</span>
        <span class="status-value">{{ status.total_chunks || 0 }}</span>
      </div>
      <el-button
        size="small"
        type="primary"
        :loading="indexing"
        :disabled="textbooks.length === 0"
        @click="buildIndex"
      >
        {{ status.total_chunks ? '重建索引' : '建立索引' }}
      </el-button>
    </div>

    <div class="query-section">
      <el-input
        v-model="queryText"
        type="textarea"
        :rows="3"
        placeholder="输入您的问题..."
        @keydown.enter.prevent.exact="handleQuery"
      />
      <div class="query-options">
        <el-checkbox v-model="useHybrid" size="small">混合检索</el-checkbox>
        <el-checkbox v-model="useRerank" size="small">Rerank 重排</el-checkbox>
        <el-button
          type="primary"
          :loading="querying"
          :disabled="!queryText.trim() || !status.total_chunks"
          @click="handleQuery"
        >
          提问
        </el-button>
      </div>
    </div>

    <div v-if="response" class="response-section">
      <div class="response-header">
        <span>💡 回答</span>
        <span class="response-time">
          {{ response.total_time.toFixed(2) }}s
          (检索 {{ response.retrieval_time.toFixed(2) }}s + 生成 {{ response.generation_time.toFixed(2) }}s)
        </span>
      </div>
      <div class="response-text">{{ response.answer }}</div>

      <div v-if="response.citations.length > 0" class="citations-section">
        <div class="section-title">📚 引用来源</div>
        <div
          v-for="(cite, idx) in response.citations"
          :key="cite.chunk_id"
          class="citation"
        >
          <div class="citation-source">
            [{{ idx + 1 }}] 《{{ cite.textbook_name }}》 · {{ cite.chapter_title }}
            <span v-if="cite.page_number">· 第 {{ cite.page_number }} 页</span>
            <span class="citation-score">
              相关度：{{ (cite.relevance_score * 100).toFixed(0) }}%
            </span>
          </div>
          <div class="citation-snippet">{{ cite.text_snippet }}</div>
        </div>
      </div>

      <div v-if="response.token_usage?.input_tokens" class="token-usage">
        Token 消耗：输入 {{ response.token_usage.input_tokens }} ·
        输出 {{ response.token_usage.output_tokens }}
      </div>
    </div>

    <div v-if="!response && !querying" class="empty-state" style="padding: 20px;">
      <div style="font-size: 32px;">❓</div>
      <div>暂无问答记录</div>
      <div style="font-size: 12px; margin-top: 4px;">输入问题开始提问</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { ragApi } from '../services/api.js';

const props = defineProps({
  textbooks: { type: Array, default: () => [] },
});

const queryText = ref('');
const useHybrid = ref(true);
const useRerank = ref(true);
const querying = ref(false);
const indexing = ref(false);
const response = ref(null);
const status = ref({ total_textbooks: 0, total_chunks: 0 });

async function loadStatus() {
  try {
    status.value = await ragApi.status();
  } catch (error) {
    console.error('Failed to load status:', error);
  }
}

async function buildIndex() {
  if (props.textbooks.length === 0) {
    ElMessage.warning('请先上传教材');
    return;
  }
  indexing.value = true;
  try {
    const ids = props.textbooks.map((t) => t.textbook_id);
    const result = await ragApi.buildIndex(ids);
    ElMessage.success(result.message);
    await loadStatus();
  } catch (error) {
    ElMessage.error(`索引建立失败：${error.message}`);
  } finally {
    indexing.value = false;
  }
}

async function handleQuery() {
  if (!queryText.value.trim()) return;
  if (!status.value.total_chunks) {
    ElMessage.warning('请先建立索引');
    return;
  }

  querying.value = true;
  try {
    response.value = await ragApi.query(queryText.value, {
      useHybridSearch: useHybrid.value,
      useRerank: useRerank.value,
    });
  } catch (error) {
    ElMessage.error(`查询失败：${error.message}`);
  } finally {
    querying.value = false;
  }
}

onMounted(() => {
  loadStatus();
});
</script>

<style scoped>
.rag-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  padding: 16px 18px;
}

.rag-status {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elev) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  flex-wrap: wrap;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rag-status:hover {
  border-color: var(--border-strong);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
}

.status-item {
  display: flex;
  align-items: baseline;
}

.status-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.status-value {
  font-weight: 700;
  color: var(--accent);
  margin-left: 4px;
  font-size: 14px;
  letter-spacing: -0.2px;
}

.rag-status .el-button {
  margin-left: auto;
}

.query-section {
  margin-bottom: 18px;
  flex-shrink: 0;
}

.query-section :deep(.el-textarea__inner) {
  border-radius: var(--radius-md);
  border-color: var(--border);
  resize: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.query-section :deep(.el-textarea__inner:focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}

.query-options {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 10px;
}

.query-options .el-button {
  margin-left: auto;
}

.response-section {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elev) 100%);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-lg);
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.response-section:hover {
  border-color: var(--accent);
  box-shadow: 0 8px 24px rgba(96, 165, 250, 0.1);
}

.response-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}

.response-time {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 400;
}

.response-text {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--text-primary);
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.3) 0%, rgba(0, 0, 0, 0.2) 100%);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
  font-size: 14px;
  max-height: 400px;
  overflow-y: auto;
  word-break: break-word;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2);
}

.citations-section {
  margin-top: 16px;
}

.citation-score {
  float: right;
  font-size: 11px;
  font-weight: 500;
  color: var(--warning);
}

.citation-snippet {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  line-height: 1.55;
}

.token-usage {
  font-size: 11px;
  color: var(--text-tertiary);
  text-align: right;
  margin-top: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-primary);
  letter-spacing: 0.1px;
}
</style>
