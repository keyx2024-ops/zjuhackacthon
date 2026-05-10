<template>
  <div class="graph-container">
    <div v-if="!graphData || graphData.nodes.length === 0" class="empty-state">
      <div class="empty-state-icon">🌐</div>
      <div>暂无知识图谱</div>
      <div style="font-size: 12px; margin-top: 4px;">
        请选择一本教材或执行整合操作
      </div>
    </div>

    <div v-else>
      <div class="graph-toolbar">
        <el-button-group size="small">
          <el-button :type="layout === 'cose' ? 'primary' : 'default'" @click="changeLayout('cose')">
            力导向图
          </el-button>
          <el-button :type="layout === 'concentric' ? 'primary' : 'default'" @click="changeLayout('concentric')">
            同心图
          </el-button>
          <el-button :type="layout === 'breadthfirst' ? 'primary' : 'default'" @click="changeLayout('breadthfirst')">
            层级图
          </el-button>
        </el-button-group>
        <el-input
          v-model="searchQuery"
          placeholder="搜索节点..."
          size="small"
          clearable
          style="width: 200px; margin-left: 12px;"
          @input="handleSearch"
        />
        <el-button size="small" @click="resetView" style="margin-left: 8px;">重置</el-button>
        <span class="graph-stats">
          {{ graphData.nodes.length }} 节点 · {{ graphData.edges.length }} 关系
        </span>
      </div>

      <div ref="cyContainer" class="cy-canvas"></div>

      <transition name="fade">
        <div v-if="selectedNode" class="node-info-panel">
          <div class="node-info-header">
            <span class="node-info-title">{{ selectedNode.label }}</span>
            <el-button size="small" link @click="selectedNode = null">×</el-button>
          </div>
          <div class="node-info-section">
            <div class="info-label">类别</div>
            <el-tag size="small">{{ selectedNode.category }}</el-tag>
          </div>
          <div class="node-info-section">
            <div class="info-label">定义</div>
            <div>{{ selectedNode.definition }}</div>
          </div>
          <div class="node-info-section" v-if="selectedNode.aliases?.length">
            <div class="info-label">别名</div>
            <div>{{ selectedNode.aliases.join(', ') }}</div>
          </div>
          <div class="node-info-section">
            <div class="info-label">来源</div>
            <div>《{{ selectedNode.textbook_name }}》</div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ selectedNode.chapter_title }}
              <span v-if="selectedNode.page_number">· 第 {{ selectedNode.page_number }} 页</span>
            </div>
          </div>
          <div class="node-info-section" v-if="selectedNode.frequency > 1">
            <div class="info-label">频次</div>
            <div>在 {{ selectedNode.frequency }} 本教材中出现</div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import cytoscape from 'cytoscape';

const props = defineProps({
  graphData: Object,
  isIntegrated: Boolean,
});

const emit = defineEmits(['node-clicked']);

const cyContainer = ref(null);
const cy = ref(null);
const layout = ref('cose');
const searchQuery = ref('');
const selectedNode = ref(null);

const TEXTBOOK_COLORS = [
  '#409eff',
  '#67c23a',
  '#e6a23c',
  '#f56c6c',
  '#909399',
  '#8e44ad',
  '#16a085',
];

function getTextbookColor(textbookId) {
  if (!textbookId) return '#909399';
  let hash = 0;
  for (let i = 0; i < textbookId.length; i++) {
    hash = textbookId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return TEXTBOOK_COLORS[Math.abs(hash) % TEXTBOOK_COLORS.length];
}

function initCytoscape() {
  if (!cyContainer.value || !props.graphData) return;

  if (cy.value) {
    cy.value.destroy();
  }

  cy.value = cytoscape({
    container: cyContainer.value,
    elements: [
      ...props.graphData.nodes.map((node) => ({
        data: {
          ...node.data,
          color: getTextbookColor(node.data.textbook_id),
        },
      })),
      ...props.graphData.edges,
    ],
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          label: 'data(label)',
          color: '#2c3e50',
          'font-size': '12px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 4,
          width: 'data(size)',
          height: 'data(size)',
          'text-wrap': 'wrap',
          'text-max-width': '120px',
          'border-width': 2,
          'border-color': '#ffffff',
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#ff4757',
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': '#c0c4cc',
          'target-arrow-color': '#c0c4cc',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': '10px',
          color: '#909399',
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
        },
      },
    ],
    layout: getLayoutOptions(layout.value),
    minZoom: 0.2,
    maxZoom: 3,
  });

  cy.value.on('tap', 'node', (event) => {
    const node = event.target;
    selectedNode.value = node.data();
    emit('node-clicked', node.data());
  });

  cy.value.on('tap', (event) => {
    if (event.target === cy.value) {
      selectedNode.value = null;
    }
  });
}

function getLayoutOptions(layoutName) {
  const layouts = {
    cose: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      animate: true,
      animationDuration: 500,
    },
    concentric: {
      name: 'concentric',
      animate: true,
      animationDuration: 500,
      concentric: (node) => node.degree(),
      levelWidth: () => 1,
    },
    breadthfirst: {
      name: 'breadthfirst',
      animate: true,
      animationDuration: 500,
      directed: true,
    },
  };
  return layouts[layoutName] || layouts.cose;
}

function changeLayout(newLayout) {
  layout.value = newLayout;
  if (cy.value) {
    cy.value.layout(getLayoutOptions(newLayout)).run();
  }
}

function handleSearch() {
  if (!cy.value) return;
  const query = searchQuery.value.toLowerCase().trim();

  cy.value.nodes().forEach((node) => {
    if (!query) {
      node.style('opacity', 1);
    } else {
      const label = (node.data('label') || '').toLowerCase();
      const definition = (node.data('definition') || '').toLowerCase();
      const matches = label.includes(query) || definition.includes(query);
      node.style('opacity', matches ? 1 : 0.2);
    }
  });

  cy.value.edges().forEach((edge) => {
    const sourceVisible = edge.source().style('opacity') > 0.5;
    const targetVisible = edge.target().style('opacity') > 0.5;
    edge.style('opacity', sourceVisible && targetVisible ? 1 : 0.1);
  });
}

function resetView() {
  searchQuery.value = '';
  if (cy.value) {
    cy.value.nodes().style('opacity', 1);
    cy.value.edges().style('opacity', 1);
    cy.value.fit(undefined, 50);
    cy.value.center();
  }
}

watch(
  () => props.graphData,
  () => {
    nextTick(() => {
      initCytoscape();
    });
  },
  { deep: true }
);

onMounted(() => {
  if (props.graphData) {
    initCytoscape();
  }
});

onUnmounted(() => {
  if (cy.value) {
    cy.value.destroy();
  }
});
</script>

<style scoped>
.graph-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
}

.graph-stats {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
}

.cy-canvas {
  position: absolute;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
}

.node-info-panel {
  position: absolute;
  top: 70px;
  right: 16px;
  width: 320px;
  max-height: calc(100% - 90px);
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 16px;
  overflow-y: auto;
  z-index: 100;
}

.node-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.node-info-title {
  font-size: 16px;
  font-weight: 600;
}

.node-info-section {
  margin-bottom: 12px;
  font-size: 13px;
}

.info-label {
  font-weight: 500;
  color: #606266;
  margin-bottom: 4px;
  font-size: 12px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
