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
          <el-button :type="layout === 'cose-bilkent' ? 'primary' : 'default'" @click="changeLayout('cose-bilkent')">
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
import { ref, watch, onMounted, onUnmounted } from 'vue';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';

cytoscape.use(coseBilkent);

const props = defineProps({
  graphData: Object,
  isIntegrated: Boolean,
});

const emit = defineEmits(['node-clicked']);

const cyContainer = ref(null);
const cy = ref(null);
const layout = ref('cose-bilkent');
const searchQuery = ref('');
const selectedNode = ref(null);
const searchTimer = ref(null);
const suppressNextContainerClear = ref(false);
const containerClickHandler = ref(null);

const TEXTBOOK_COLORS = [
  '#409eff',
  '#67c23a',
  '#e6a23c',
  '#f56c6c',
  '#909399',
  '#8e44ad',
  '#16a085',
];

const RELATION_LABEL_ZH = {
  prerequisite: '前置',
  parallel: '并列',
  contains: '包含',
  applies_to: '应用',
  depends_on: '依赖',
};

function getTextbookColor(textbookId) {
  if (!textbookId) return '#909399';
  let hash = 0;
  for (let i = 0; i < textbookId.length; i++) {
    hash = textbookId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return TEXTBOOK_COLORS[Math.abs(hash) % TEXTBOOK_COLORS.length];
}

function buildEdgeLabel(edgeData = {}) {
  const rawLabel = edgeData.label || edgeData.relation_en || '';
  const relEn = String(edgeData.relation_en || String(rawLabel).split('\n')[0] || '').trim();
  const relZh = String(edgeData.relation_zh || RELATION_LABEL_ZH[relEn] || '').trim();

  if (relEn && relZh) return `${relEn}\n${relZh}`;
  if (relEn) return relEn;
  if (relZh) return relZh;

  return String(rawLabel).trim();
}

function buildElements() {
  if (!props.graphData) return [];
  return [
    ...props.graphData.nodes.map((node) => ({
      data: {
        ...node.data,
        color: getTextbookColor(node.data.textbook_id),
      },
    })),
    ...props.graphData.edges.map((edge) => ({
      ...edge,
      data: {
        ...edge.data,
        label: buildEdgeLabel(edge.data),
      },
    })),
  ];
}

function clearEdgeFocusState() {
  if (!cy.value) return;
  cy.value.batch(() => {
    cy.value.elements().removeClass('node-muted edge-context edge-muted edge-focus');
    cy.value.elements().unselect();
  });
}

function clearInteractionState() {
  clearEdgeFocusState();
  selectedNode.value = null;
}


function initCytoscape() {
  if (!cyContainer.value || !props.graphData) return;

  cy.value = cytoscape({
    container: cyContainer.value,
    elements: buildElements(),
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          label: 'data(label)',
          color: '#f1f5f9',
          'font-size': '12px',
          'font-weight': 600,
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 10,
          width: 'data(size)',
          height: 'data(size)',
          'min-zoomed-font-size': 10,
          'text-wrap': 'wrap',
          'text-overflow-wrap': 'anywhere',
          'text-max-width': '120px',
          'line-height': 1.2,
          'border-width': 2,
          'border-color': '#ffffff',
          'text-background-color': 'transparent',
          'text-background-opacity': 0,
          'z-index-compare': 'manual',
          'z-index': 40,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#60a5fa',
          'box-shadow': '0 0 12px rgba(96, 165, 250, 0.6)',
          'z-index-compare': 'manual',
          'z-index': 5,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 2,
          'line-color': '#4d5a73',
          'target-arrow-color': '#4d5a73',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 11,
          'min-zoomed-font-size': 9,
          color: '#cbd5e1',
          'line-height': 1.25,
          'text-wrap': 'wrap',
          'text-max-width': '180px',
          'text-events': 'yes',
          'text-margin-y': -14,
          'text-rotation': 'none',
          'text-background-color': 'transparent',
          'text-background-opacity': 0,
          'z-index-compare': 'manual',
          'z-index': 60,
        },
      },
      {
        selector: 'edge:selected',
        style: {
          width: 2.8,
          'line-color': '#60a5fa',
          'target-arrow-color': '#60a5fa',
          color: '#ffffff',
          'font-size': 12,
          'line-height': 1.3,
          'text-outline-width': 1,
          'text-outline-color': 'rgba(0, 0, 0, 0.35)',
          'text-background-color': 'transparent',
          'text-background-opacity': 0,
          'z-index-compare': 'manual',
          'z-index': 9999,
        },
      },
      {
        selector: '.dimmed',
        style: {
          opacity: 0.15,
        },
      },
      {
        selector: '.matched',
        style: {
          opacity: 1,
        },
      },
      {
        selector: 'node.node-muted',
        style: {
          opacity: 0.12,
          'text-opacity': 0.08,
        },
      },
      {
        selector: 'node.edge-context',
        style: {
          opacity: 1,
          'text-opacity': 1,
          'z-index-compare': 'manual',
          'z-index': 50000,
        },
      },
      {
        selector: 'edge.edge-muted',
        style: {
          opacity: 0.05,
        },
      },
      {
        selector: 'edge.edge-focus',
        style: {
          opacity: 1,
          width: 3.2,
          'line-color': '#60a5fa',
          'target-arrow-color': '#60a5fa',
          color: '#ffffff',
          'font-size': 12,
          'line-height': 1.3,
          'text-outline-width': 1,
          'text-outline-color': 'rgba(0, 0, 0, 0.35)',
          'text-margin-y': -10,
          'z-index-compare': 'manual',
          'z-index': 100000,
        },
      },
    ],
    layout: getLayoutOptions(layout.value),
    minZoom: 0.2,
    maxZoom: 3,
  });

  cy.value.on('tap', 'node', (event) => {
    suppressNextContainerClear.value = true;
    const node = event.target;
    node.select();
    selectedNode.value = node.data();
    emit('node-clicked', node.data());
  });

  cy.value.on('tap', 'edge', (event) => {
    suppressNextContainerClear.value = true;
    const edge = event.target;
    clearEdgeFocusState();
    cy.value.batch(() => {
      const source = edge.source();
      const target = edge.target();
      edge.select();
      edge.addClass('edge-focus');
      source.addClass('edge-context');
      target.addClass('edge-context');

      cy.value.nodes().not(source).not(target).addClass('node-muted');
      cy.value.edges().not(edge).addClass('edge-muted');
    });
    selectedNode.value = null;
  });

  cy.value.on('tap', (event) => {
    if (event.target === cy.value) {
      clearInteractionState();
      suppressNextContainerClear.value = true;
    }
  });

  containerClickHandler.value = (e) => {
    if (suppressNextContainerClear.value) {
      suppressNextContainerClear.value = false;
      return;
    }
    if (!(e.target instanceof Element)) return;
    if (e.target.closest('.node-info-panel')) return;
    clearInteractionState();
  };

  cyContainer.value.addEventListener('click', containerClickHandler.value);
}

function refreshGraphElements() {
  if (!cy.value || !props.graphData) return;
  cy.value.batch(() => {
    cy.value.elements().remove();
    cy.value.add(buildElements());
  });
  cy.value.layout(getLayoutOptions(layout.value)).run();
}
function getLayoutOptions(layoutName) {
  const layouts = {
    'cose-bilkent': {
      name: 'cose-bilkent',
      quality: 'default',
      randomize: false,
      animate: false,
      fit: true,
      padding: 64,
      nodeDimensionsIncludeLabels: true,
      tile: false,
      nodeRepulsion: 9000,
      idealEdgeLength: 180,
      edgeElasticity: 0.35,
      nestingFactor: 0.1,
      gravity: 0.5,
      numIter: 1400,
      gravityRangeCompound: 1.5,
      gravityCompound: 1.0,
      gravityRange: 3.8,
    },
    concentric: {
      name: 'concentric',
      animate: false,
      concentric: (node) => node.degree(),
      levelWidth: () => 1,
    },
    breadthfirst: {
      name: 'breadthfirst',
      animate: false,
      directed: true,
    },
  };
  return layouts[layoutName] || layouts['cose-bilkent'];
}

function changeLayout(newLayout) {
  if (layout.value === newLayout) return;
  layout.value = newLayout;
  if (cy.value) {
    cy.value.layout(getLayoutOptions(newLayout)).run();
  }
}

function applySearch(query) {
  if (!cy.value) return;
  cy.value.batch(() => {
    const all = cy.value.elements();
    all.removeClass('dimmed');
    all.removeClass('matched');

    if (!query) {
      return;
    }

    cy.value.nodes().forEach((node) => {
      const label = (node.data('label') || '').toLowerCase();
      const definition = (node.data('definition') || '').toLowerCase();
      const matches = label.includes(query) || definition.includes(query);
      if (matches) {
        node.addClass('matched');
      } else {
        node.addClass('dimmed');
      }
    });

    cy.value.edges().forEach((edge) => {
      const sourceMatched = edge.source().hasClass('matched');
      const targetMatched = edge.target().hasClass('matched');
      if (sourceMatched && targetMatched) {
        edge.addClass('matched');
      } else {
        edge.addClass('dimmed');
      }
    });
  });
}

function handleSearch() {
  if (!cy.value) return;
  if (searchTimer.value) {
    clearTimeout(searchTimer.value);
  }
  searchTimer.value = setTimeout(() => {
    const query = searchQuery.value.toLowerCase().trim();
    applySearch(query);
  }, 180);
}

function resetView() {
  searchQuery.value = '';
  if (searchTimer.value) {
    clearTimeout(searchTimer.value);
    searchTimer.value = null;
  }
  if (cy.value) {
    cy.value.batch(() => {
      const all = cy.value.elements();
      all.removeClass('dimmed');
      all.removeClass('matched');
      all.removeClass('node-muted');
      all.removeClass('edge-context');
      all.removeClass('edge-muted');
      all.removeClass('edge-focus');
      all.unselect();
    });
    selectedNode.value = null;
    cy.value.fit(undefined, 50);
    cy.value.center();
  }
}

watch(
  () => props.graphData,
  (newGraphData) => {
    if (!newGraphData) return;
    if (!cy.value) {
      initCytoscape();
      return;
    }
    refreshGraphElements();
    applySearch(searchQuery.value.toLowerCase().trim());
  }
);

onMounted(() => {
  if (props.graphData) {
    initCytoscape();
  }
});

onUnmounted(() => {
  if (searchTimer.value) {
    clearTimeout(searchTimer.value);
    searchTimer.value = null;
  }
  if (cyContainer.value && containerClickHandler.value) {
    cyContainer.value.removeEventListener('click', containerClickHandler.value);
    containerClickHandler.value = null;
  }
  if (cy.value) {
    cy.value.destroy();
    cy.value = null;
  }
});
</script>

<style scoped>
.graph-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  gap: 12px;
}

.graph-stats {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.cy-canvas {
  position: absolute;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-app);
}

.node-info-panel {
  position: absolute;
  top: 70px;
  right: 16px;
  width: 320px;
  max-height: calc(100% - 90px);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elev) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 16px;
  overflow-y: auto;
  z-index: 100;
  color: var(--text-primary);
}

.node-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.node-info-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.node-info-section {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.info-label {
  font-weight: 500;
  color: var(--text-tertiary);
  margin-bottom: 4px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
