<template>
  <div>
    <div class="target-card">
      <div class="target-header">
        <span class="target-label">目标压缩比</span>
        <span class="target-value">{{ (innerRatio * 100).toFixed(0) }}%</span>
      </div>
      <el-slider
        :model-value="innerRatio * 100"
        @update:model-value="onSliderChange"
        :min="10"
        :max="30"
        :step="1"
        :format-tooltip="(v) => v + '%'"
        :disabled="progress && progress.status === 'running'"
      />
      <div class="target-hint">
        数值越小越精炼，可能删除更多低重要性节点
      </div>
    </div>

    <div v-if="progress && progress.status === 'running'" class="progress-card">
      <div class="progress-header">
        <span class="progress-phase">{{ progress.phase || '处理中' }}</span>
        <span class="progress-percent">{{ progress.percent ? progress.percent.toFixed(0) : 0 }}%</span>
      </div>
      <el-progress
        :percentage="progress.percent || 0"
        :stroke-width="10"
        :show-text="false"
        status="success"
      />
      <div class="progress-message">{{ progress.message || '...' }}</div>
      <div class="progress-elapsed">已用时 {{ progress.elapsed || 0 }} s</div>
    </div>

    <div v-else-if="!integrationResult" class="empty-state">
      <div class="empty-state-icon">🔄</div>
      <div>暂无整合结果</div>
      <div style="font-size: 12px; margin-top: 4px;">
        请在左侧选择 2 本以上教材并点击"开始整合"
      </div>
    </div>

    <div v-else>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label-top">教材总字数</div>
          <div class="stat-value-num">{{ integrationResult.original_total_words.toLocaleString() }}</div>
        </div>
        <div class="stat-card stat-card-accent">
          <div class="stat-label-top">整合后字数</div>
          <div class="stat-value-num">{{ integrationResult.integrated_total_words.toLocaleString() }}</div>
        </div>
      </div>

      <div class="compression-section">
        <div class="compression-label">
          <span>压缩比</span>
          <span class="compression-value">
            {{ (integrationResult.compression_ratio * 100).toFixed(2) }}%
          </span>
        </div>
        <div class="compression-bar">
          <div
            class="compression-bar-fill"
            :style="{ width: Math.min(integrationResult.compression_ratio * 100, 100) + '%' }"
          ></div>
        </div>
        <div class="compression-target">
          <span :class="{ 'on-target': integrationResult.compression_ratio <= (integrationResult.target_ratio || 0.30) }">
            目标 ≤ {{ ((integrationResult.target_ratio || 0.30) * 100).toFixed(0) }}%
            · {{ integrationResult.compression_ratio <= (integrationResult.target_ratio || 0.30) ? '已达标' : '未达标' }}
          </span>
        </div>
        <div
          v-if="integrationResult.original_kp_count"
          class="kp-retention"
        >
          知识点保留 {{ integrationResult.integrated_kp_count }} / {{ integrationResult.original_kp_count }}
          （{{ ((integrationResult.integrated_kp_count / integrationResult.original_kp_count) * 100).toFixed(1) }}%）
        </div>
      </div>

      <div class="decision-summary">
        <div class="section-title-sm">决策摘要</div>
        <div class="summary-grid">
          <div class="summary-item merge">
            <div class="summary-count">{{ integrationResult.decisions_summary.merge_count }}</div>
            <div class="summary-label">合并</div>
          </div>
          <div class="summary-item keep">
            <div class="summary-count">{{ integrationResult.decisions_summary.keep_count }}</div>
            <div class="summary-label">保留</div>
          </div>
          <div class="summary-item remove">
            <div class="summary-count">{{ integrationResult.decisions_summary.remove_count }}</div>
            <div class="summary-label">删除</div>
          </div>
        </div>
      </div>

      <div v-if="decisions.length > 0" class="decisions-list">
        <div class="section-title-sm decisions-title">
          整合决策详情
          <el-button size="small" @click="loadDecisions" link>刷新</el-button>
        </div>
        <div
          v-for="decision in decisions.slice(0, 20)"
          :key="decision.action_id"
          class="decision-card"
          :class="decision.decision"
        >
          <div class="decision-type">
            <strong>{{ getDecisionLabel(decision.decision) }}</strong>
            <span v-if="decision.is_user_modified" class="user-modified-badge">教师修改</span>
          </div>
          <div class="decision-reason">{{ decision.reason }}</div>
        </div>
        <div v-if="decisions.length > 20" class="decisions-more">
          ··· 还有 {{ decisions.length - 20 }} 条
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { integrationApi } from '../services/api.js';

const props = defineProps({
  integrationResult: Object,
  progress: Object,
  targetRatio: { type: Number, default: 0.30 },
});

const emit = defineEmits(['decisions-loaded', 'update:targetRatio']);

const decisions = ref([]);

const innerRatio = computed(() => props.targetRatio ?? 0.30);

function onSliderChange(percent) {
  const ratio = Math.max(0.05, Math.min(percent / 100, 1));
  emit('update:targetRatio', ratio);
}

async function loadDecisions() {
  if (!props.integrationResult) return;
  try {
    const result = await integrationApi.getDecisions(props.integrationResult.result_id);
    decisions.value = result.decisions;
    emit('decisions-loaded', decisions.value);
  } catch (error) {
    ElMessage.error(`加载决策失败：${error.message}`);
  }
}

function getDecisionLabel(decision) {
  const labels = {
    merge: '🔗 合并',
    keep: '✅ 保留',
    remove: '🗑️ 删除',
  };
  return labels[decision] || decision;
}

watch(
  () => props.integrationResult,
  (newVal) => {
    if (newVal) {
      loadDecisions();
    }
  }
);
</script>

<style scoped>
.target-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 14px 16px 8px;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
  transition: border-color 0.15s ease;
}
.target-card:hover {
  border-color: var(--border-strong);
}
.target-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}
.target-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.target-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.3px;
}
.target-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
  line-height: 1.5;
}

.target-card :deep(.el-slider__runway) {
  background: var(--border);
  height: 4px;
}
.target-card :deep(.el-slider__bar) {
  background: var(--accent);
  height: 4px;
}
.target-card :deep(.el-slider__button) {
  width: 16px;
  height: 16px;
  border: 2px solid var(--accent);
  background: white;
}

.kp-retention {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

.progress-card {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.progress-phase {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.progress-percent {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.3px;
}
.progress-message {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 10px;
  line-height: 1.5;
  word-break: break-all;
}
.progress-elapsed {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.progress-card :deep(.el-progress-bar__outer) {
  background: var(--border);
}
.progress-card :deep(.el-progress-bar__inner) {
  background: var(--accent);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-card-accent {
  background: var(--accent-soft);
  border-color: var(--accent-ring);
}
.stat-card-accent:hover {
  border-color: var(--accent);
}
.stat-label-top {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 500;
}
.stat-value-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.4px;
  line-height: 1.2;
}

.compression-section {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.compression-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.compression-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.4px;
}

.compression-target {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

.compression-target .on-target {
  color: var(--success);
  font-weight: 500;
}

.section-title-sm {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-primary);
  letter-spacing: 0.1px;
}
.decisions-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 18px;
}

.summary-item {
  text-align: center;
  padding: 14px 8px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: transform 0.15s ease;
}
.summary-item:hover {
  transform: translateY(-1px);
}

.summary-item.merge {
  background: var(--success-soft);
  color: var(--success);
}

.summary-item.keep {
  background: var(--accent-soft);
  color: var(--accent);
}

.summary-item.remove {
  background: var(--danger-soft);
  color: var(--danger);
}

.summary-count {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.summary-label {
  font-size: 12px;
  margin-top: 2px;
  opacity: 0.85;
}

.decisions-more {
  text-align: center;
  padding: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.decision-type {
  margin-bottom: 4px;
  color: var(--text-primary);
}

.decision-reason {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.user-modified-badge {
  display: inline-block;
  background: var(--danger);
  color: white;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  margin-left: 8px;
  font-weight: 500;
}
</style>
