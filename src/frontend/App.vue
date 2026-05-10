<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ collapsed: leftCollapsed }">
      <div class="header">
        <span class="header-title">📚 学科知识整合智能体</span>
        <button class="header-toggle" @click="leftCollapsed = true" title="收起左栏">
          <el-icon><Fold /></el-icon>
        </button>
      </div>
      <TextbookManager
        :textbooks="textbooks"
        :selected-id="selectedTextbookId"
        @uploaded="onUploaded"
        @selected="onTextbookSelected"
        @deleted="onTextbookDeleted"
        @integrate="onIntegrate"
      />
    </aside>

    <button
      v-if="leftCollapsed"
      class="float-toggle left"
      @click="leftCollapsed = false"
      title="展开教材栏"
    >
      <el-icon><Expand /></el-icon>
    </button>

    <div class="main-area">
      <KnowledgeGraph
        ref="graphRef"
        :graph-data="currentGraphData"
        :is-integrated="isIntegratedView"
        @node-clicked="onNodeClicked"
      />
    </div>

    <button
      v-if="rightCollapsed"
      class="float-toggle right"
      @click="rightCollapsed = false"
      title="展开操作面板"
    >
      <el-icon><Fold /></el-icon>
    </button>

    <aside class="right-panel" :class="{ collapsed: rightCollapsed }">
      <div class="panel-header">
        <button class="header-toggle" @click="rightCollapsed = true" title="收起右栏">
          <el-icon><Expand /></el-icon>
        </button>
        <span class="panel-header-title">操作面板</span>
      </div>
      <el-tabs v-model="activeTab" class="panel-tabs">
        <el-tab-pane label="整合操作" name="integration">
          <IntegrationPanel
            :integration-result="integrationResult"
            :progress="integrationProgress"
            v-model:target-ratio="targetRatio"
            @decisions-loaded="onDecisionsLoaded"
          />
        </el-tab-pane>
        <el-tab-pane label="RAG 问答" name="rag">
          <RAGPanel :textbooks="textbooks" />
        </el-tab-pane>
        <el-tab-pane label="多轮对话" name="dialogue">
          <DialoguePanel
            :integration-result="integrationResult"
            @decisions-modified="loadIntegration"
          />
        </el-tab-pane>
      </el-tabs>
    </aside>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
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
const activeTab = ref('integration');
const isIntegratedView = ref(false);
const graphRef = ref(null);
const leftCollapsed = ref(false);
const rightCollapsed = ref(false);
const lastUploadedId = ref(null);
const targetRatio = ref(0.30);

async function loadTextbooks() {
  try {
    const result = await textbookApi.list();
    textbooks.value = result.textbooks;
  } catch (error) {
    ElMessage.error(`加载教材列表失败：${error.message}`);
  }
}

async function onUploaded(textbookId) {
  if (textbookId) lastUploadedId.value = textbookId;
  await loadTextbooks();
}

async function onTextbookSelected(textbookId) {
  selectedTextbookId.value = textbookId;
  isIntegratedView.value = false;

  try {
    let result;
    try {
      result = await graphApi.getByTextbook(textbookId);
    } catch (error) {
      ElMessage.info('正在为教材构建知识图谱，请稍候...');
      result = await graphApi.build(textbookId);
    }
    currentGraphData.value = result.data;
  } catch (error) {
    ElMessage.error(`加载知识图谱失败：${error.message}`);
  }
}

function onTextbookDeleted(textbookId) {
  if (selectedTextbookId.value === textbookId) {
    selectedTextbookId.value = null;
    currentGraphData.value = null;
  }
  loadTextbooks();
}

async function onIntegrate(textbookIds) {
  try {
    integrationProgress.value = {
      status: 'running',
      phase: '准备中',
      percent: 0,
      message: `开始整合 ${textbookIds.length} 本教材（目标 ≤ ${(targetRatio.value * 100).toFixed(0)}%）`,
    };
    activeTab.value = 'integration';
    if (rightCollapsed.value) rightCollapsed.value = false;

    const startResp = await integrationApi.start(textbookIds, targetRatio.value);
    const jobId = startResp.job_id;

    const result = await pollProgress(jobId);
    integrationResult.value = result;
    currentGraphData.value = result.graph_data;
    isIntegratedView.value = true;
    integrationProgress.value = null;
    ElMessage.success(
      `整合完成！压缩比：${(result.compression_ratio * 100).toFixed(1)}%`
    );
  } catch (error) {
    integrationProgress.value = null;
    ElMessage.error(`整合失败：${error.message}`);
  }
}

function pollProgress(jobId) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
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
        setTimeout(tick, 1500);
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
    currentGraphData.value = result.graph_data;
    isIntegratedView.value = true;
  } catch (error) {
    if (!error.message.includes('not')) {
      ElMessage.error(`加载整合结果失败：${error.message}`);
    }
  }
}

function onDecisionsLoaded() {}

function onNodeClicked(node) {}

defineExpose({ lastUploadedId });

onMounted(() => {
  loadTextbooks();
});
</script>
