<template>
  <div class="integration-container">

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
          <span>字数压缩比</span>
          <span class="compression-value">
            {{ (contestCompressionRatio * 100).toFixed(2) }}%
          </span>
        </div>
        <div class="compression-bar">
          <div
            class="compression-bar-fill"
            :style="{ width: Math.min(contestCompressionRatio * 100, 100) + '%' }"
          ></div>
        </div>
        <div class="compression-target">
          <span :class="{ 'on-target': contestCompressionRatio <= (integrationResult.target_ratio || 0.30) }">
            计算：{{ contestRatioNumerator.toLocaleString() }} / {{ contestRatioDenominator.toLocaleString() }}
            = {{ (contestCompressionRatio * 100).toFixed(2) }}%
            · 目标 ≤ {{ ((integrationResult.target_ratio || 0.30) * 100).toFixed(0) }}%
            · {{ contestCompressionRatio <= (integrationResult.target_ratio || 0.30) ? '已达标' : '未达标' }}
          </span>
        </div>

        <div v-if="kpRatioDenominator > 0" class="compression-label kp-label">
          <span>知识点完整度</span>
          <span class="compression-value kp-value">
            {{ (kpCompleteness * 100).toFixed(1) }}%
          </span>
        </div>
        <div v-if="kpRatioDenominator > 0" class="compression-bar kp-bar">
          <div
            class="compression-bar-fill kp-bar-fill"
            :style="{ width: Math.min(kpCompleteness * 100, 100) + '%' }"
          ></div>
        </div>
        <div v-if="kpRatioDenominator > 0" class="compression-target">
          计算：总知识点 {{ kpRatioNumerator }} / (合并+保留-删除) {{ kpRatioDenominator }} = {{ (kpCompleteness * 100).toFixed(2) }}%
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

      <div v-if="integrationResult" class="decisions-list">
        <div class="section-title-sm decisions-title">
          整合决策详情
          <el-button size="small" @click="loadDecisions" link>刷新</el-button>
        </div>
        <div v-if="decisions.length === 0" class="decisions-more">暂无决策详情，可点击刷新</div>
        <template v-else>
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
            <div v-if="decisionsTotal > 20" class="decisions-more">
            ··· 还有 {{ decisionsTotal - 20 }} 条
          </div>
        </template>
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
});

const emit = defineEmits(['decisions-loaded']);

const decisions = ref([]);
const decisionsTotal = ref(0);

const contestRatioNumerator = computed(() => {
  const backendVal = props.integrationResult?.contest_ratio_numerator;
  if (typeof backendVal === 'number') return backendVal;
  return props.integrationResult?.integrated_total_words || 0;
});

const contestRatioDenominator = computed(() => {
  const backendVal = props.integrationResult?.contest_ratio_denominator;
  if (typeof backendVal === 'number') return backendVal;
  return props.integrationResult?.original_total_words || 0;
});

const contestCompressionRatio = computed(() => {
  const backendVal = props.integrationResult?.contest_compression_ratio;
  if (typeof backendVal === 'number') return backendVal;
  if (contestRatioDenominator.value <= 0) return 0;
  return contestRatioNumerator.value / contestRatioDenominator.value;
});

const kpRatioNumerator = computed(() => {
  const backendVal = props.integrationResult?.kp_ratio_numerator;
  if (typeof backendVal === 'number') return backendVal;
  const summary = props.integrationResult?.decisions_summary || {};
  return summary.total || 0;
});

const kpRatioDenominator = computed(() => {
  const backendVal = props.integrationResult?.kp_ratio_denominator;
  if (typeof backendVal === 'number') return backendVal;
  const summary = props.integrationResult?.decisions_summary || {};
  return (summary.merge_count || 0) + (summary.keep_count || 0) - (summary.remove_count || 0);
});

const kpCompleteness = computed(() => {
  if (kpRatioDenominator.value <= 0) return 0;
  return kpRatioNumerator.value / kpRatioDenominator.value;
});

async function loadDecisions() {
  if (!props.integrationResult) return;

  if (Array.isArray(props.integrationResult.decisions)) {
    const all = props.integrationResult.decisions;
    decisionsTotal.value = all.length;
    decisions.value = all.slice(0, 20);
    emit('decisions-loaded', { total: decisionsTotal.value });
    return;
  }

  try {
    const result = await integrationApi.getDecisions(props.integrationResult.result_id);
    const all = Array.isArray(result.decisions) ? result.decisions : [];
    decisionsTotal.value = all.length;
    decisions.value = all.slice(0, 20);
    emit('decisions-loaded', { total: decisionsTotal.value });
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
  () => props.integrationResult?.result_id,
  (resultId) => {
    if (resultId) {
      loadDecisions();
    } else {
      decisions.value = [];
      decisionsTotal.value = 0;
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.integration-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 18px;
}


.kp-retention {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

.progress-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elev) 100%);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
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
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elev) 100%);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.compression-section:hover {
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(96, 165, 250, 0.1);
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

.kp-label {
  margin-top: 14px;
}

.kp-value {
  color: var(--warning);
}

.kp-bar .compression-bar-fill.kp-bar-fill {
  background: linear-gradient(90deg, #fbbf24 0%, #f59e0b 100%);
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.35);
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
  padding: 16px 12px;
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.1) 100%);
  box-shadow: var(--shadow-xs);
}

.summary-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
}

.summary-item.merge {
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.2) 0%, rgba(52, 211, 153, 0.1) 100%);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.summary-item.merge:hover {
  border-color: var(--success);
  box-shadow: 0 8px 20px rgba(52, 211, 153, 0.2);
}

.summary-item.keep {
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.2) 0%, rgba(96, 165, 250, 0.1) 100%);
  color: var(--accent);
  border-color: rgba(96, 165, 250, 0.3);
}

.summary-item.keep:hover {
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(96, 165, 250, 0.2);
}

.summary-item.remove {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.2) 0%, rgba(248, 113, 113, 0.1) 100%);
  color: var(--danger);
  border-color: rgba(248, 113, 113, 0.3);
}

.summary-item.remove:hover {
  border-color: var(--danger);
  box-shadow: 0 8px 20px rgba(248, 113, 113, 0.2);
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
