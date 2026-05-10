<template>
  <div class="section upload-section">
    <el-upload
      class="upload-compact"
      drag
      :auto-upload="true"
      :http-request="customUpload"
      :show-file-list="false"
      multiple
      accept=".pdf,.docx,.md,.txt"
    >
      <div class="upload-inner">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <div class="upload-title">拖拽或点击上传教材</div>
          <div class="upload-hint">PDF · DOCX · MD · TXT</div>
        </div>
      </div>
    </el-upload>
  </div>

  <div class="section textbook-list-section">
    <div class="section-title">
      <span>已上传教材<span class="count-badge">{{ textbooks.length }}</span></span>
      <el-button
        v-if="textbooks.length >= 2"
        type="primary"
        size="small"
        @click="handleIntegrate"
      >
        开始整合
      </el-button>
    </div>

    <div v-if="textbooks.length === 0" class="empty-state">
      <div class="empty-state-icon">📚</div>
      <div>暂无教材</div>
      <div class="empty-hint">上传文件开始构建知识图谱</div>
    </div>

    <div
      v-for="textbook in textbooks"
      :key="textbook.textbook_id"
      class="textbook-item"
      :class="{ active: selectedId === textbook.textbook_id }"
      @click="$emit('selected', textbook.textbook_id)"
    >
      <div class="textbook-name">{{ textbook.name }}</div>
      <div class="textbook-meta">
        {{ textbook.file_format.toUpperCase() }} ·
        {{ textbook.chapters.length }} 章 ·
        {{ textbook.total_words.toLocaleString() }} 字
      </div>
      <div class="textbook-actions">
        <el-checkbox
          v-model="selectedForIntegration"
          :label="textbook.textbook_id"
          @click.stop
        >
          整合
        </el-checkbox>
        <el-button
          link
          size="small"
          @click.stop="toggleChapters(textbook.textbook_id)"
        >
          {{ expanded[textbook.textbook_id] ? '收起章节' : '查看章节' }}
        </el-button>
        <el-button
          type="danger"
          size="small"
          link
          class="delete-btn"
          @click.stop="handleDelete(textbook.textbook_id)"
        >
          删除
        </el-button>
      </div>

      <div
        v-if="expanded[textbook.textbook_id]"
        class="chapter-list"
        @click.stop
      >
        <div
          v-for="(ch, idx) in textbook.chapters"
          :key="ch.chapter_id || idx"
          class="chapter-row"
        >
          <span class="chapter-num">{{ ch.chapter_number || (idx + 1) }}</span>
          <span class="chapter-title" :title="ch.title">{{ ch.title }}</span>
          <span class="chapter-meta">
            <template v-if="ch.page_start">P{{ ch.page_start }}<template v-if="ch.page_end && ch.page_end !== ch.page_start">-{{ ch.page_end }}</template> · </template>
            {{ (ch.word_count || 0).toLocaleString() }} 字
          </span>
        </div>
        <div v-if="!textbook.chapters.length" class="chapter-empty">未识别到章节</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import { textbookApi } from '../services/api.js';

const props = defineProps({
  textbooks: { type: Array, default: () => [] },
  selectedId: String,
});

const emit = defineEmits(['uploaded', 'selected', 'deleted', 'integrate']);

const selectedForIntegration = ref([]);
const expanded = ref({});
const knownIds = ref(new Set());

watch(
  () => props.textbooks,
  (list) => {
    const currentIds = new Set(list.map((t) => t.textbook_id));
    const newIds = [...currentIds].filter((id) => !knownIds.value.has(id));

    if (list.length === 1) {
      expanded.value = { ...expanded.value, [list[0].textbook_id]: true };
    } else if (newIds.length > 0) {
      const next = { ...expanded.value };
      for (const id of newIds) next[id] = true;
      expanded.value = next;
    }

    knownIds.value = currentIds;
  },
  { immediate: true, deep: true }
);

function toggleChapters(textbookId) {
  expanded.value = { ...expanded.value, [textbookId]: !expanded.value[textbookId] };
}

async function customUpload(options) {
  const { file } = options;
  try {
    ElMessage.info(`正在解析 ${file.name}...`);
    const resp = await textbookApi.upload(file);
    ElMessage.success(`${file.name} 上传成功`);
    emit('uploaded', resp?.textbook_id);
  } catch (error) {
    ElMessage.error(`上传失败：${error.message}`);
  }
}

async function handleDelete(textbookId) {
  try {
    await ElMessageBox.confirm('确定删除该教材？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await textbookApi.delete(textbookId);
    ElMessage.success('删除成功');
    emit('deleted', textbookId);
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(`删除失败：${error.message}`);
    }
  }
}

function handleIntegrate() {
  const ids = Array.isArray(selectedForIntegration.value)
    ? selectedForIntegration.value
    : [];
  if (ids.length < 2) {
    if (props.textbooks.length >= 2) {
      emit(
        'integrate',
        props.textbooks.map((t) => t.textbook_id)
      );
    } else {
      ElMessage.warning('请至少选择 2 本教材进行整合');
    }
    return;
  }
  emit('integrate', ids);
}
</script>

<style scoped>
.upload-section {
  padding: 14px 18px !important;
}

.upload-compact :deep(.el-upload) {
  width: 100%;
}

.upload-compact :deep(.el-upload-dragger) {
  width: 100%;
  height: auto;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1.5px dashed var(--border-strong);
  background: var(--bg-elev);
  transition: all 0.18s ease;
}

.upload-compact :deep(.el-upload-dragger:hover) {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.upload-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
}

.upload-icon {
  font-size: 22px;
  color: var(--text-tertiary);
  flex: 0 0 auto;
}

.upload-text {
  flex: 1;
  min-width: 0;
}

.upload-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.upload-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
  letter-spacing: 0.2px;
}

.textbook-list-section {
  flex: 1;
  overflow-y: auto;
}

.count-badge {
  display: inline-block;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  margin-left: 6px;
  letter-spacing: 0.2px;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.textbook-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.delete-btn {
  margin-left: auto;
}

.chapter-list {
  margin-top: 10px;
  padding: 10px;
  background: var(--bg-elev);
  border-radius: var(--radius-sm);
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border);
}
.chapter-row {
  display: flex;
  align-items: baseline;
  font-size: 12px;
  padding: 5px 0;
  border-bottom: 1px dashed var(--border);
  gap: 8px;
}
.chapter-row:last-child {
  border-bottom: none;
}
.chapter-num {
  flex: 0 0 24px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.chapter-title {
  flex: 1;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chapter-meta {
  flex: 0 0 auto;
  color: var(--text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}
.chapter-empty {
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
  padding: 8px;
}
</style>
