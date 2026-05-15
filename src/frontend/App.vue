<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ collapsed: leftCollapsed }">
      <div class="header">
        <div class="header-top">
          <span class="header-title">📚 学科知识整合智能体</span>
          <button class="header-toggle" @click="leftCollapsed = true" title="收起左栏">
            <el-icon><Fold /></el-icon>
          </button>
        </div>
        <div class="top-nav">
          <button
            v-for="item in navItems"
            :key="item.key"
            class="top-nav-item"
            :class="{ active: activeNav === item.key }"
            @click="onNavClick(item.key)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="sidebar-content single-module-content">
        <div class="sidebar-section module-section" v-if="activeNav === 'upload'">
          <TextbookManager
            ref="textbookManagerRef"
            mode="manage"
            :textbooks="textbooks"
            :selected-id="selectedTextbookId"
            @uploaded="onUploaded"
            @selected="onTextbookSelected"
            @deleted="onTextbookDeleted"
            @integrate="onIntegrate"
            @compress="onCompress"
          />
        </div>

        <div class="sidebar-section module-section" v-else-if="activeNav === 'integration'">
          <IntegrationPanel
            :integration-result="integrationResult"
            :progress="integrationProgress"
            @decisions-loaded="onDecisionsLoaded"
          />
        </div>

        <div class="sidebar-section module-section" v-else-if="activeNav === 'rag'">
          <RAGPanel :textbooks="textbooks" />
        </div>

        <div class="sidebar-section module-section" v-else>
          <DialoguePanel
            :integration-result="integrationResult"
            @decisions-modified="loadIntegration"
          />
        </div>
      </div>
    </aside>

    <button
      v-if="leftCollapsed"
      class="float-toggle left"
      @click="leftCollapsed = false"
      title="展开左栏"
    >
      <el-icon><Expand /></el-icon>
    </button>

    <div class="main-area">
      <KnowledgeGraph
        :key="graphRenderKey"
        ref="graphRef"
        :graph-data="currentGraphData"
        :is-integrated="isIntegratedView"
        :build-progress="graphBuildProgress"
        :integration-result="integrationResult"
        :textbooks="textbooks"
        @node-clicked="onNodeClicked"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { Fold, Expand } from '@element-plus/icons-vue';
import { textbookApi, graphApi, integrationApi } from './services/api.js';
import TextbookManager from './components/TextbookManager.vue';
import KnowledgeGraph from './components/KnowledgeGraph.vue';
import IntegrationPanel from './components/IntegrationPanel.vue';
import RAGPanel from './components/RAGPanel.vue';
import DialoguePanel from './components/DialoguePanel.vue';

const textbooks = ref([]);
const selectedTextbookId = ref(null);
const currentGraphData = ref(null);
const integrationResult = ref(null);
const integrationProgress = ref(null);
const activeNav = ref('upload');
const isIntegratedView = ref(false);
const navItems = [
  { key: 'upload', label: '我的教材' },
  { key: 'integration', label: '整合图谱' },
  { key: 'rag', label: 'RAG问答' },
  { key: 'dialogue', label: '多轮对话' },
];
const graphRef = ref(null);
const textbookManagerRef = ref(null);
const leftCollapsed = ref(false);
const lastUploadedId = ref(null);
const pollTimer = ref(null);
const pollToken = ref(0);
const graphBuildTimer = ref(null);
const graphBuildPollToken = ref(0);
const manualTextbookView = ref(false);
const textbookLoadToken = ref(0);
const graphVersion = ref(0);
const graphBuildProgress = ref(null);

const graphRenderKey = computed(() => {
  if (isIntegratedView.value) {
    return `integrated:${integrationResult.value?.result_id || 'latest'}:${graphVersion.value}`;
  }
  return `textbook:${selectedTextbookId.value || 'none'}:${graphVersion.value}`;
});

function normalizeGraphData(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (Array.isArray(payload.nodes) && Array.isArray(payload.edges)) return payload;
  if (payload.data && Array.isArray(payload.data.nodes) && Array.isArray(payload.data.edges)) return payload.data;
  if (payload.graph_data && Array.isArray(payload.graph_data.nodes) && Array.isArray(payload.graph_data.edges)) return payload.graph_data;
  return null;
}

async function loadTextbooks() {
  try {
    const result = await textbookApi.list();
    textbooks.value = result.textbooks;
  } catch (error) {
    ElMessage.error(`加载教材列表失败：${error.message}`);
  }
}

async function onUploaded(payload) {
  const textbookId = payload?.textbookId || payload;
  const jobId = payload?.jobId || null;
  if (textbookId) lastUploadedId.value = textbookId;
  await loadTextbooks();
  if (!textbookId) return;

  manualTextbookView.value = true;
  selectedTextbookId.value = textbookId;
  isIntegratedView.value = false;
  currentGraphData.value = null;
  graphVersion.value += 1;

  if (!jobId) return;

  graphBuildProgress.value = { status: 'running', phase: '提取知识点并构建图谱', current: 0, total: 1, percent: 0, message: '任务已启动...' };
  try {
    const result = await pollGraphBuild(jobId, textbookId);
    if (!result) return;
    const normalized = normalizeGraphData(result);
    if (normalized) {
      currentGraphData.value = normalized;
      graphVersion.value += 1;
      ElMessage.success('教材图谱生成完成');
    }
  } catch (error) {
    ElMessage.error(`生成知识图谱失败：${error.message}`);
  } finally {
    graphBuildProgress.value = null;
  }
}

async function onTextbookSelected(textbookId) {
  const token = ++textbookLoadToken.value;
  manualTextbookView.value = true;
  selectedTextbookId.value = textbookId;
  isIntegratedView.value = false;
  currentGraphData.value = null;
  graphVersion.value += 1;

  graphBuildProgress.value = { status: 'running', phase: '加载教材图谱', current: 0, total: 100, percent: 10, message: '正在请求数据...' };

  try {
    const result = await graphApi.getByTextbook(textbookId);
    if (token !== textbookLoadToken.value) return;
    graphBuildProgress.value = { status: 'running', phase: '加载教材图谱', current: 50, total: 100, percent: 50, message: '数据已返回，解析中...' };
    const normalized = normalizeGraphData(result);
    if (normalized) {
      graphBuildProgress.value = null;
      currentGraphData.value = normalized;
    } else {
      console.warn('[onTextbookSelected] normalizeGraphData returned null. Raw result keys:', Object.keys(result || {}), 'data keys:', Object.keys(result?.data || {}));
      graphBuildProgress.value = { status: 'running', phase: '加载教材图谱', current: 0, total: 100, percent: 0, message: '图谱数据格式异常，尝试重新构建...' };
      const buildResp = await graphApi.build(textbookId, { force: true });
      if (token !== textbookLoadToken.value) return;
      await handleBuildResponse(buildResp, textbookId, token);
    }
  } catch (error) {
    if (token !== textbookLoadToken.value) return;
    const msg = String(error?.message || '').toLowerCase();
    if (msg.includes('not found') || msg.includes('404')) {
      graphBuildProgress.value = { status: 'running', phase: '构建教材图谱', current: 0, total: 1, percent: 0, message: '图谱不存在，开始构建...' };
      try {
        const buildResp = await graphApi.build(textbookId);
        if (token !== textbookLoadToken.value) return;
        await handleBuildResponse(buildResp, textbookId, token);
      } catch (buildError) {
        ElMessage.error(`生成知识图谱失败：${buildError.message}`);
        graphBuildProgress.value = null;
      }
    } else {
      ElMessage.error(`加载知识图谱失败：${error.message}`);
      graphBuildProgress.value = null;
    }
  }
}

async function handleBuildResponse(buildResp, textbookId, token) {
  if (buildResp.status === 'completed') {
    const normalized = normalizeGraphData(buildResp.result);
    if (normalized) {
      graphBuildProgress.value = null;
      currentGraphData.value = normalized;
    } else {
      graphBuildProgress.value = null;
    }
    return;
  }
  const result = await pollGraphBuild(buildResp.job_id, textbookId);
  if (!result) { graphBuildProgress.value = null; return; }
  if (token !== textbookLoadToken.value) return;
  const normalized = normalizeGraphData(result);
  if (normalized) {
    graphBuildProgress.value = null;
    currentGraphData.value = normalized;
    ElMessage.success('教材图谱生成完成');
  } else {
    graphBuildProgress.value = null;
  }
}

function pollGraphBuild(jobId, textbookId) {
  graphBuildPollToken.value += 1;
  const currentToken = graphBuildPollToken.value;

  if (graphBuildTimer.value) {
    clearTimeout(graphBuildTimer.value);
    graphBuildTimer.value = null;
  }

  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (currentToken !== graphBuildPollToken.value) {
        resolve(null);
        return;
      }
      if (selectedTextbookId.value !== textbookId) {
        resolve(null);
        return;
      }

      try {
        const state = await graphApi.getBuildProgress(jobId);
        graphBuildProgress.value = state;

        if (state.status === 'completed') {
          resolve(state.result);
          return;
        }
        if (state.status === 'failed') {
          reject(new Error(state.error || '图谱构建失败'));
          return;
        }
        graphBuildTimer.value = setTimeout(tick, 1500);
      } catch (error) {
        reject(error);
      }
    };
    tick();
  });
}

function onTextbookDeleted(textbookId) {
  if (selectedTextbookId.value === textbookId) {
    selectedTextbookId.value = null;
    currentGraphData.value = null;
  }
  loadTextbooks();
}

async function runIntegration(textbookIds, targetRatio = null) {
  integrationProgress.value = {
    status: 'running',
    phase: '准备中',
    percent: 0,
    message: targetRatio
      ? `开始压缩 ${textbookIds.length} 本教材（目标 ≤ ${(targetRatio * 100).toFixed(0)}%）`
      : `开始整合 ${textbookIds.length} 本教材（自动保留更多知识点）`,
  };
  activeNav.value = 'integration';

  const startResp = await integrationApi.start(textbookIds, targetRatio);
  const jobId = startResp.job_id;
  const result = await pollProgress(jobId);

  integrationResult.value = result;
  currentGraphData.value = normalizeGraphData(result);
  if (!currentGraphData.value) {
    throw new Error('整合图谱数据结构异常');
  }
  graphVersion.value += 1;
  isIntegratedView.value = true;
  manualTextbookView.value = false;
  integrationProgress.value = null;
  return result;
}

async function onIntegrate(textbookIds) {
  try {
    const result = await runIntegration(textbookIds, null);
    const ratio = result.contest_compression_ratio ?? result.compression_ratio ?? 0;

    if (ratio > 0.30) {
      ElMessage.warning(`当前压缩比 ${(ratio * 100).toFixed(1)}%，已超过 30%，请选择压缩目标`);
      textbookManagerRef.value?.openCompressionDialog(30);
      return;
    }

    ElMessage.success(`整合完成！压缩比：${(ratio * 100).toFixed(1)}%`);
  } catch (error) {
    integrationProgress.value = null;
    ElMessage.error(`整合失败：${error.message}`);
  }
}

async function onCompress(payload) {
  const textbookIds = Array.isArray(payload) ? payload : payload.textbookIds;
  const targetRatio = Array.isArray(payload) ? 0.30 : payload.targetRatio;

  try {
    const result = await runIntegration(textbookIds, targetRatio);
    const ratio = result.contest_compression_ratio ?? result.compression_ratio ?? 0;
    ElMessage.success(`压缩完成！压缩比：${(ratio * 100).toFixed(1)}%`);
  } catch (error) {
    integrationProgress.value = null;
    ElMessage.error(`压缩失败：${error.message}`);
  }
}

function pollProgress(jobId) {
  pollToken.value += 1;
  const token = pollToken.value;

  if (pollTimer.value) {
    clearTimeout(pollTimer.value);
    pollTimer.value = null;
  }

  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (token !== pollToken.value) {
        reject(new Error('轮询已取消'));
        return;
      }

      try {
        const state = await integrationApi.getProgress(jobId);
        integrationProgress.value = state;
        if (state.status === 'completed') {
          resolve(state.result);
          return;
        }
        if (state.status === 'failed') {
          reject(new Error(state.error || '后台任务失败'));
          return;
        }
        pollTimer.value = setTimeout(tick, 1500);
      } catch (e) {
        reject(e);
      }
    };
    tick();
  });
}

async function loadIntegration() {
  try {
    const result = await integrationApi.getLatest();
    integrationResult.value = result;

    if (!manualTextbookView.value) {
      const graph = normalizeGraphData(result);
      if (graph) {
        currentGraphData.value = graph;
        graphVersion.value += 1;
        isIntegratedView.value = true;
        activeNav.value = 'integration';
      }
    }
  } catch (error) {
    if (!error.message.includes('not')) {
      ElMessage.error(`加载整合结果失败：${error.message}`);
    }
  }
}

function onDecisionsLoaded() {}

function onNodeClicked(node) {}

async function onNavClick(key) {
  if (key === 'integration') {
    if (integrationResult.value) {
      activeNav.value = key;
      const graph = normalizeGraphData(integrationResult.value);
      if (graph) {
        currentGraphData.value = graph;
        isIntegratedView.value = true;
        manualTextbookView.value = false;
      }
      return;
    }
    try {
      const result = await integrationApi.getLatest();
      integrationResult.value = result;
      activeNav.value = key;
      const graph = normalizeGraphData(result);
      if (graph) {
        currentGraphData.value = graph;
        isIntegratedView.value = true;
        manualTextbookView.value = false;
      }
    } catch (error) {
      ElMessage.warning('请先整合 2 份及以上教材');
    }
    return;
  }
  activeNav.value = key;
}

defineExpose({ lastUploadedId });

onMounted(async () => {
  await loadTextbooks();
  if (textbooks.value.length === 1) {
    onTextbookSelected(textbooks.value[0].textbook_id);
  } else if (textbooks.value.length > 1) {
    await loadIntegration();
  }
});

onUnmounted(() => {
  pollToken.value += 1;
  graphBuildPollToken.value += 1;
  if (pollTimer.value) {
    clearTimeout(pollTimer.value);
    pollTimer.value = null;
  }
  if (graphBuildTimer.value) {
    clearTimeout(graphBuildTimer.value);
    graphBuildTimer.value = null;
  }
});
</script>
