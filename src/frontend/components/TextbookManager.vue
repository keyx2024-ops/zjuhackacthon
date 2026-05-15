<template>
  <div v-if="props.mode === 'manage'" class="section upload-section">
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

  <el-dialog
    v-model="showCompressionDialog"
    title="压缩超过 30%"
    width="460px"
    :close-on-click-modal="false"
    append-to-body
  >
    <div class="integration-dialog-body">
      <div class="ratio-row">
        <span class="ratio-label">目标压缩比</span>
        <span class="ratio-value">{{ targetRatioPercent }}%</span>
      </div>
      <el-slider
        v-model="targetRatioPercent"
        :min="10"
        :max="30"
        :step="1"
        :format-tooltip="(v) => v + '%'"
      />
      <div class="ratio-hint">当前整合结果高于 30%，可选择压缩到目标值以下</div>
    </div>
    <template #footer>
      <el-button @click="showCompressionDialog = false">取消</el-button>
      <el-button type="primary" @click="confirmCompression">确认压缩</el-button>
    </template>
  </el-dialog>

  <div class="section textbook-list-section">
    <div class="section-title">
      <span>{{ props.mode === 'preview' ? '教材预览' : '已上传教材' }}<span class="count-badge">{{ textbooks.length }}</span></span>
      <div class="title-actions" v-if="props.mode === 'manage'">
        <el-button
          v-if="textbooks.length > 0"
          size="small"
          link
          @click="toggleAllChapters"
        >
          {{ allExpanded ? '全部收起' : '全部展开' }}
        </el-button>
        <el-button
          v-if="textbooks.length > 1"
          size="small"
          link
          @click="toggleSelectAll"
        >
          {{ selectedForIntegration.length === textbooks.length ? '取消全选' : '全选' }}
        </el-button>
        <el-button
          v-if="textbooks.length >= 2"
          type="primary"
          size="small"
          @click="openIntegrationDialog"
        >
          开始整合
        </el-button>
      </div>
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
          v-if="props.mode === 'manage'"
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
          v-if="props.mode === 'manage'"
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
import { ref, watch, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import { textbookApi } from '../services/api.js';

const props = defineProps({
  textbooks: { type: Array, default: () => [] },
  selectedId: String,
  mode: { type: String, default: 'manage' },
});

const emit = defineEmits(['uploaded', 'selected', 'deleted', 'integrate', 'compress']);

const selectedForIntegration = ref([]);
const expanded = ref({});
const knownIds = ref(new Set());
const showCompressionDialog = ref(false);
const targetRatioPercent = ref(30);

const allExpanded = computed(() => {
  return props.textbooks.length > 0 && props.textbooks.every(t => expanded.value[t.textbook_id]);
});

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

function toggleAllChapters() {
  const newState = !allExpanded.value;
  const next = { ...expanded.value };
  for (const textbook of props.textbooks) {
    next[textbook.textbook_id] = newState;
  }
  expanded.value = next;
}

function toggleSelectAll() {
  if (selectedForIntegration.value.length === props.textbooks.length) {
    selectedForIntegration.value = [];
  } else {
    selectedForIntegration.value = props.textbooks.map(t => t.textbook_id);
  }
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

function openIntegrationDialog() {
  if (props.textbooks.length < 2) {
    ElMessage.warning('请至少选择 2 本教材进行整合');
    return;
  }
  const ids = Array.isArray(selectedForIntegration.value)
    ? selectedForIntegration.value
    : [];
  const selectedIds = ids.length < 2
    ? props.textbooks.map((t) => t.textbook_id)
    : ids;
  emit('integrate', selectedIds);
}

function openCompressionDialog(defaultPercent = 30) {
  targetRatioPercent.value = Math.max(10, Math.min(30, defaultPercent));
  showCompressionDialog.value = true;
}

function confirmCompression() {
  const ids = Array.isArray(selectedForIntegration.value)
    ? selectedForIntegration.value
    : [];
  const selectedIds = ids.length < 2
    ? props.textbooks.map((t) => t.textbook_id)
    : ids;

  showCompressionDialog.value = false;
  emit('compress', {
    textbookIds: selectedIds,
    targetRatio: targetRatioPercent.value / 100,
  });
}

defineExpose({ openCompressionDialog });
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

.title-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
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

.integration-dialog-body {
  padding-top: 4px;
}

.ratio-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.ratio-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ratio-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
}

.ratio-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
