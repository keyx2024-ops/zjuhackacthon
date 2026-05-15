<template>
  <div class="graph-container">
    <div v-if="buildProgress && buildProgress.status === 'running'" class="empty-state">
      <div class="empty-state-icon">⏳</div>
      <div>{{ buildProgress.phase || '正在生成知识图谱' }}</div>
      <div style="font-size: 12px; margin-top: 4px;">
        {{ buildProgress.message || '正在处理中...' }}
      </div>
      <div class="progress-bar-wrapper">
        <div class="progress-bar-track">
          <div class="progress-bar-fill" :style="{ width: (buildProgress.percent || 0) + '%' }"></div>
        </div>
        <span class="progress-bar-text">{{ typeof buildProgress.percent === 'number' ? buildProgress.percent.toFixed(1) : '0.0' }}%</span>
      </div>
      <div v-if="buildProgress.total > 1" style="font-size: 11px; margin-top: 4px; color: #64748b;">
        {{ buildProgress.current || 0 }}/{{ buildProgress.total || 0 }} 章
      </div>
    </div>

    <div v-else-if="!graphData || !Array.isArray(graphData.nodes) || graphData.nodes.length === 0" class="empty-state">
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
        <el-button size="small" type="success" :loading="exportLoading" @click="exportHTML" style="margin-left: 8px;">
          {{ exportLoading ? '导出中...' : '导出' }}
        </el-button>
        <span class="graph-stats">
          {{ graphData.nodes.length }} 节点 · {{ graphData.edges.length }} 关系
        </span>
      </div>

      <div ref="cyContainer" class="cy-canvas"></div>

      <div v-if="isIntegrated && legendItems.length > 1" class="graph-legend">
        <div
          v-for="item in legendItems"
          :key="item.id"
          class="legend-item"
        >
          <span class="legend-dot" :style="{ background: item.color }"></span>
          <span class="legend-label">{{ item.name }}</span>
        </div>
      </div>

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
import { ref, computed, watch, watchEffect, onMounted, onUnmounted, nextTick } from 'vue';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import cytoscapeSrc from '../../../node_modules/cytoscape/dist/cytoscape.min.js?raw';

cytoscape.use(fcose);

const props = defineProps({
  graphData: Object,
  isIntegrated: Boolean,
  buildProgress: Object,
  integrationResult: Object,
  textbooks: { type: Array, default: () => [] },
});

const emit = defineEmits(['node-clicked']);

const cyContainer = ref(null);
const cy = ref(null);
const layout = ref('cose-bilkent');
const searchQuery = ref('');
const selectedNode = ref(null);
const searchTimer = ref(null);
const positionCache = ref({});
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

const legendItems = computed(() => {
  if (!props.graphData || !props.isIntegrated) return [];
  const map = new Map();
  for (const node of props.graphData.nodes) {
    const tbId = node.data?.textbook_id;
    const tbName = node.data?.textbook_name;
    if (tbId && tbName && !map.has(tbId)) {
      map.set(tbId, { id: tbId, name: tbName, color: getTextbookColor(tbId) });
    }
  }
  return [...map.values()];
});

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
  const nodeIds = new Set(props.graphData.nodes.map(n => n.data.id));
  const validEdges = props.graphData.edges.filter(e =>
    nodeIds.has(e.data.source) && nodeIds.has(e.data.target)
  );
  return [
    ...props.graphData.nodes.map((node) => ({
      data: {
        ...node.data,
        color: getTextbookColor(node.data.textbook_id),
      },
    })),
    ...validEdges.map((edge) => ({
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
  if (!props.graphData) { console.warn('[KG] initCytoscape: no graphData'); return; }
  if (cy.value) { console.warn('[KG] initCytoscape: cy already exists'); return; }
  if (!cyContainer.value) {
    console.warn('[KG] initCytoscape: container not ready, retrying...');
    nextTick(() => {
      if (cyContainer.value && !cy.value) initCytoscape();
      else console.warn('[KG] initCytoscape retry: container=', !!cyContainer.value, 'cy=', !!cy.value);
    });
    return;
  }
  console.log('[KG] initCytoscape: starting with', props.graphData.nodes.length, 'nodes');

  loadCachedPositions();
  const cachedPositions = positionCache.value[layout.value];
  const usePreset = cachedPositions && Object.keys(cachedPositions).length > 0;

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
          'min-zoomed-font-size': 14,
          'text-wrap': 'ellipsis',
          'text-max-width': '100px',
          'border-width': 2,
          'border-color': '#ffffff',
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
          width: 1.5,
          'line-color': '#4d5a73',
          'target-arrow-color': '#4d5a73',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 11,
          'min-zoomed-font-size': 10,
          color: '#cbd5e1',
          'text-wrap': 'wrap',
          'text-max-width': '160px',
          'text-margin-y': -12,
          'text-rotation': 'none',
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
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          label: 'data(label)',
          color: '#ffffff',
          'font-size': 12,
          'text-wrap': 'wrap',
          'text-max-width': '180px',
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
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'line-color': '#60a5fa',
          'target-arrow-color': '#60a5fa',
          label: 'data(label)',
          color: '#ffffff',
          'font-size': 12,
          'text-wrap': 'wrap',
          'text-max-width': '180px',
          'z-index-compare': 'manual',
          'z-index': 100000,
        },
      },
    ],
    layout: usePreset
      ? { name: 'preset', positions: (node) => cachedPositions[node.id()] || { x: 0, y: 0 } }
      : { name: 'grid', animate: false },
    minZoom: 0.2,
    maxZoom: 3,
    textureOnViewport: true,
  });

  if (!usePreset) {
    setTimeout(() => {
      if (!cy.value) return;
      const layoutOpts = getLayoutOptions(layout.value);
      layoutOpts.stop = () => cachePositions();
      cy.value.layout(layoutOpts).run();
    }, 50);
  } else {
    cy.value.fit(undefined, 50);
  }

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

  positionCache.value = {};

  cy.value.batch(() => {
    cy.value.elements().remove();
    cy.value.add(buildElements());
  });
  const layoutOpts = getLayoutOptions(layout.value);
  layoutOpts.stop = () => cachePositions();
  cy.value.layout(layoutOpts).run();
}
function getLayoutOptions(layoutName) {
  const layouts = {
    'cose-bilkent': {
      name: 'fcose',
      quality: 'default',
      randomize: true,
      animate: false,
      fit: true,
      padding: 64,
      nodeDimensionsIncludeLabels: true,
      nodeRepulsion: () => 9000,
      idealEdgeLength: () => 180,
      edgeElasticity: () => 0.35,
      gravity: 0.5,
      numIter: 2500,
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
  if (!cy.value) return;

  const cached = positionCache.value[newLayout];
  if (cached && Object.keys(cached).length > 0) {
    cy.value.layout({
      name: 'preset',
      positions: (node) => cached[node.id()] || { x: 0, y: 0 },
      fit: true,
      padding: 50,
    }).run();
  } else {
    const layoutOpts = getLayoutOptions(newLayout);
    layoutOpts.stop = () => cachePositions();
    cy.value.layout(layoutOpts).run();
  }
}

function getStorageKey() {
  if (props.isIntegrated && props.integrationResult?.result_id) {
    return `kg_pos_integrated_${props.integrationResult.result_id}`;
  }
  if (!props.isIntegrated && props.graphData?.nodes?.length > 0) {
    const firstNode = props.graphData.nodes[0];
    const tbId = firstNode?.data?.textbook_id;
    if (tbId) return `kg_pos_textbook_${tbId}`;
  }
  return null;
}

function cachePositions() {
  if (!cy.value) return;
  const positions = {};
  cy.value.nodes().forEach(n => {
    positions[n.id()] = { ...n.position() };
  });
  positionCache.value[layout.value] = positions;

  const storageKey = getStorageKey();
  if (storageKey) {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
      stored[layout.value] = positions;
      localStorage.setItem(storageKey, JSON.stringify(stored));
    } catch (e) { /* quota exceeded or other error */ }
  }
}

function loadCachedPositions() {
  const storageKey = getStorageKey();
  if (!storageKey) return;
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
    if (stored && typeof stored === 'object') {
      positionCache.value = stored;
    }
  } catch (e) { /* ignore */ }
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

const LAYOUT_ZH_NAME = {
  'cose-bilkent': '力导向图',
  'concentric': '同心图',
  'breadthfirst': '层级图',
};

const exportLoading = ref(false);

function exportHTML() {
  if (!props.graphData || exportLoading.value) return;
  if (!cy.value) return;
  exportLoading.value = true;

  setTimeout(() => {
    try {
      const layoutZh = LAYOUT_ZH_NAME[layout.value] || '力导向图';

      const positionedData = {
        nodes: cy.value.nodes().map(n => ({
          data: n.data(),
          position: n.position(),
        })),
        edges: cy.value.edges().map(e => ({ data: e.data() })),
      };
      const graphJson = JSON.stringify(positionedData);
      const safeJson = graphJson.replace(/<\/script/gi, '<\\/script').replace(/<!--/g, '<\\!--');

      const sidebarData = {
        integration: props.integrationResult ? {
          compressionRatio: props.integrationResult.contest_compression_ratio ?? props.integrationResult.compression_ratio,
          targetRatio: props.integrationResult.target_ratio,
          originalKpCount: props.integrationResult.original_kp_count,
          integratedKpCount: props.integrationResult.integrated_kp_count,
          originalWords: props.integrationResult.original_total_words,
          integratedWords: props.integrationResult.integrated_total_words,
          decisionsSummary: props.integrationResult.decisions_summary || {},
        } : null,
        textbooks: props.textbooks.map(t => ({
          name: t.name,
          totalWords: t.total_words,
          chapters: t.chapters?.length || 0,
          format: t.file_format,
        })),
      };
      const sidebarJson = JSON.stringify(sidebarData).replace(/<\/script/gi, '<\\/script');

      let filename;
      if (props.isIntegrated) {
        filename = `整合-${layoutZh}.html`;
      } else {
        const tbName = props.graphData.nodes[0]?.data?.textbook_name || '教材';
        filename = `${tbName}-图谱.html`;
      }

      const html = buildExportHTML(safeJson, layoutZh, layout.value, sidebarJson);
      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      console.error('Export failed:', e);
    } finally {
      exportLoading.value = false;
    }
  }, 50);
}

function buildExportHTML(graphJson, layoutZh, layoutName, sidebarJson) {
  const activeCose = layoutName === 'cose-bilkent' ? ' active' : '';
  const activeConcentric = layoutName === 'concentric' ? ' active' : '';
  const activeBreadth = layoutName === 'breadthfirst' ? ' active' : '';
  return '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n' +
'<meta charset="UTF-8">\n' +
'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
'<title>知识图谱 - ' + layoutZh + '</title>\n' +
'<script>\n' + cytoscapeSrc + '\n</' + 'script>\n' +
'<style>\n' +
'* { margin: 0; padding: 0; box-sizing: border-box; }\n' +
'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e2e8f0; overflow: hidden; display: flex; height: 100vh; }\n' +
'#sidebar { width: 280px; min-width: 280px; background: #1e293b; border-right: 1px solid #334155; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }\n' +
'#sidebar h2 { font-size: 14px; font-weight: 600; color: #f1f5f9; margin-bottom: 8px; }\n' +
'.sidebar-section { background: #0f172a; border-radius: 8px; padding: 12px; border: 1px solid #334155; }\n' +
'.sidebar-section h3 { font-size: 12px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }\n' +
'.metric-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 13px; }\n' +
'.metric-label { color: #94a3b8; }\n' +
'.metric-value { color: #f1f5f9; font-weight: 600; }\n' +
'.metric-value.highlight { color: #3b82f6; font-size: 18px; }\n' +
'.textbook-item { padding: 8px 0; border-bottom: 1px solid #334155; font-size: 12px; }\n' +
'.textbook-item:last-child { border-bottom: none; }\n' +
'.textbook-name { font-weight: 600; color: #e2e8f0; margin-bottom: 2px; }\n' +
'.textbook-meta { color: #64748b; }\n' +
'#main { flex: 1; display: flex; flex-direction: column; position: relative; }\n' +
'#toolbar { display: flex; align-items: center; padding: 12px 16px; background: #1e293b; border-bottom: 1px solid #334155; gap: 12px; }\n' +
'.btn-group { display: flex; gap: 0; }\n' +
'.btn { padding: 6px 14px; font-size: 13px; border: 1px solid #475569; background: #1e293b; color: #cbd5e1; cursor: pointer; transition: all 0.15s; }\n' +
'.btn:first-child { border-radius: 4px 0 0 4px; }\n' +
'.btn:last-child { border-radius: 0 4px 4px 0; }\n' +
'.btn:not(:first-child) { border-left: none; }\n' +
'.btn.active { background: #3b82f6; border-color: #3b82f6; color: #fff; }\n' +
'.btn:hover:not(.active) { background: #334155; }\n' +
'#search { padding: 6px 12px; font-size: 13px; border: 1px solid #475569; border-radius: 4px; background: #0f172a; color: #e2e8f0; width: 200px; outline: none; }\n' +
'#search:focus { border-color: #3b82f6; }\n' +
'#stats { margin-left: auto; font-size: 12px; color: #64748b; }\n' +
'#cy { flex: 1; }\n' +
'#panel { display: none; position: absolute; top: 66px; right: 16px; width: 320px; max-height: calc(100% - 82px); background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; overflow-y: auto; z-index: 100; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }\n' +
'#panel.show { display: block; }\n' +
'.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #334155; }\n' +
'.panel-title { font-size: 16px; font-weight: 600; }\n' +
'.panel-close { background: none; border: none; color: #94a3b8; font-size: 20px; cursor: pointer; padding: 0 4px; }\n' +
'.panel-close:hover { color: #fff; }\n' +
'.panel-section { margin-bottom: 12px; font-size: 13px; color: #94a3b8; }\n' +
'.panel-label { font-size: 11px; font-weight: 500; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }\n' +
'.panel-tag { display: inline-block; padding: 2px 8px; background: #334155; border-radius: 4px; font-size: 12px; color: #e2e8f0; }\n' +
'.dimmed { opacity: 0.15; }\n' +
'.matched { opacity: 1; }\n' +
'.node-muted { opacity: 0.12; }\n' +
'.edge-muted { opacity: 0.05; }\n' +
'.edge-context { opacity: 1; }\n' +
'</style>\n</head>\n<body>\n' +
'<div id="sidebar">\n' +
'  <h2>知识图谱整合报告</h2>\n' +
'  <div id="sidebar-content"></div>\n' +
'</div>\n' +
'<div id="main">\n' +
'<div id="toolbar">\n' +
'  <div class="btn-group">\n' +
'    <button class="btn' + activeCose + '" onclick="changeLayout(\'cose-bilkent\')">力导向图</button>\n' +
'    <button class="btn' + activeConcentric + '" onclick="changeLayout(\'concentric\')">同心图</button>\n' +
'    <button class="btn' + activeBreadth + '" onclick="changeLayout(\'breadthfirst\')">层级图</button>\n' +
'  </div>\n' +
'  <input id="search" type="text" placeholder="搜索节点..." oninput="handleSearch(this.value)">\n' +
'  <span id="stats"></span>\n' +
'</div>\n' +
'<div id="cy"></div>\n' +
'<div id="panel">\n' +
'  <div class="panel-header">\n' +
'    <span class="panel-title" id="panel-name"></span>\n' +
'    <button class="panel-close" onclick="closePanel()">&times;</button>\n' +
'  </div>\n' +
'  <div class="panel-section"><div class="panel-label">类别</div><span class="panel-tag" id="panel-category"></span></div>\n' +
'  <div class="panel-section"><div class="panel-label">定义</div><div id="panel-definition"></div></div>\n' +
'  <div class="panel-section" id="panel-aliases-section" style="display:none"><div class="panel-label">别名</div><div id="panel-aliases"></div></div>\n' +
'  <div class="panel-section"><div class="panel-label">来源</div><div id="panel-source"></div></div>\n' +
'</div>\n' +
'</div>\n' +
'<script>\n' +
'if (typeof cytoscape === "undefined") { document.body.innerHTML = "<div style=\\"padding:40px;color:#e2e8f0;font-size:16px;\\">Cytoscape.js 加载失败。</div>"; throw new Error("cytoscape not loaded"); }\n' +
'var sidebarData = ' + sidebarJson + ';\n' +
'(function renderSidebar() {\n' +
'  var html = "";\n' +
'  var d = sidebarData.integration;\n' +
'  if (d) {\n' +
'    var ratio = d.compressionRatio ? (d.compressionRatio * 100).toFixed(1) : "N/A";\n' +
'    var target = d.targetRatio ? (d.targetRatio * 100).toFixed(0) : "N/A";\n' +
'    html += \'<div class="sidebar-section"><h3>整合指标</h3>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">压缩比</span><span class="metric-value highlight">\' + ratio + \'%</span></div>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">目标压缩比</span><span class="metric-value">\' + target + \'%</span></div>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">原始知识点</span><span class="metric-value">\' + (d.originalKpCount || 0) + \'</span></div>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">整合后知识点</span><span class="metric-value">\' + (d.integratedKpCount || 0) + \'</span></div>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">原始总字数</span><span class="metric-value">\' + (d.originalWords || 0).toLocaleString() + \'</span></div>\';\n' +
'    html += \'<div class="metric-row"><span class="metric-label">整合后字数</span><span class="metric-value">\' + (d.integratedWords || 0).toLocaleString() + \'</span></div>\';\n' +
'    var ds = d.decisionsSummary || {};\n' +
'    if (ds.total) {\n' +
'      html += \'<div class="metric-row"><span class="metric-label">合并</span><span class="metric-value">\' + (ds.merge_count || 0) + \'</span></div>\';\n' +
'      html += \'<div class="metric-row"><span class="metric-label">保留</span><span class="metric-value">\' + (ds.keep_count || 0) + \'</span></div>\';\n' +
'      html += \'<div class="metric-row"><span class="metric-label">删除</span><span class="metric-value">\' + (ds.remove_count || 0) + \'</span></div>\';\n' +
'    }\n' +
'    html += "</div>";\n' +
'  }\n' +
'  if (sidebarData.textbooks && sidebarData.textbooks.length) {\n' +
'    html += \'<div class="sidebar-section"><h3>教材列表</h3>\';\n' +
'    sidebarData.textbooks.forEach(function(t) {\n' +
'      html += \'<div class="textbook-item"><div class="textbook-name">\' + t.name + \'</div>\';\n' +
'      html += \'<div class="textbook-meta">\' + (t.format || "").toUpperCase() + " · " + t.chapters + " 章 · " + (t.totalWords || 0).toLocaleString() + " 字</div></div>";\n' +
'    });\n' +
'    html += "</div>";\n' +
'  }\n' +
'  document.getElementById("sidebar-content").innerHTML = html;\n' +
'})();\n' +
'var COLORS = ["#409eff","#67c23a","#e6a23c","#f56c6c","#909399","#8e44ad","#16a085"];\n' +
'function hashColor(id) { if (!id) return "#909399"; var h = 0; for (var i = 0; i < id.length; i++) h = id.charCodeAt(i) + ((h << 5) - h); return COLORS[Math.abs(h) % COLORS.length]; }\n' +
'var RELATION_ZH = {prerequisite:"前置",parallel:"并列",contains:"包含",applies_to:"应用",depends_on:"依赖",similar_to:"相似"};\n' +
'var graphData = ' + graphJson + ';\n' +
'var elements = graphData.nodes.map(function(n) { return { data: Object.assign({}, n.data, { color: hashColor(n.data.textbook_id) }), position: n.position }; }).concat(\n' +
'  graphData.edges.map(function(e) {\n' +
'    var d = e.data || {};\n' +
'    var en = String(d.relation_en || d.label || "").split("\\n")[0].trim();\n' +
'    var zh = d.relation_zh || RELATION_ZH[en] || "";\n' +
'    var label = en && zh ? en + "\\n" + zh : en || zh || String(d.label || "").trim();\n' +
'    return { data: Object.assign({}, d, { label: label }) };\n' +
'  })\n' +
');\n' +
'document.getElementById("stats").textContent = graphData.nodes.length + " 节点 · " + graphData.edges.length + " 关系";\n' +
'var cy = cytoscape({\n' +
'  container: document.getElementById("cy"),\n' +
'  elements: elements,\n' +
'  style: [\n' +
'    { selector: "node", style: { "background-color": "data(color)", label: "data(label)", color: "#f1f5f9", "font-size": "12px", "font-weight": 600, "text-valign": "bottom", "text-halign": "center", "text-margin-y": 10, width: "data(size)", height: "data(size)", "min-zoomed-font-size": 10, "text-wrap": "wrap", "text-max-width": "120px", "border-width": 2, "border-color": "#ffffff" } },\n' +
'    { selector: "node:selected", style: { "border-width": 4, "border-color": "#60a5fa" } },\n' +
'    { selector: "edge", style: { width: 2, "line-color": "#4d5a73", "target-arrow-color": "#4d5a73", "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)", "font-size": 11, "min-zoomed-font-size": 9, color: "#cbd5e1", "text-wrap": "wrap", "text-max-width": "180px", "text-margin-y": -14, "text-rotation": "none" } },\n' +
'    { selector: "edge:selected", style: { width: 2.8, "line-color": "#60a5fa", "target-arrow-color": "#60a5fa", color: "#ffffff", "font-size": 12 } },\n' +
'    { selector: ".edge-focus", style: { opacity: 1, width: 3.2, "line-color": "#60a5fa", "target-arrow-color": "#60a5fa", label: "data(label)", color: "#ffffff", "font-size": 12, "text-wrap": "wrap", "text-max-width": "180px", "z-index": 100000 } },\n' +
'    { selector: ".edge-context", style: { opacity: 1, "z-index": 50000 } },\n' +
'    { selector: ".node-muted", style: { opacity: 0.12 } },\n' +
'    { selector: ".edge-muted", style: { opacity: 0.05 } },\n' +
'    { selector: ".dimmed", style: { opacity: 0.15 } },\n' +
'    { selector: ".matched", style: { opacity: 1 } }\n' +
'  ],\n' +
'  layout: { name: "preset" },\n' +
'  minZoom: 0.2, maxZoom: 3\n' +
'});\n' +
'cy.fit(undefined, 50);\n' +
'cy.on("tap", "node", function(e) { clearEdgeFocus(); showPanel(e.target.data()); });\n' +
'cy.on("tap", "edge", function(e) {\n' +
'  var edge = e.target;\n' +
'  clearEdgeFocus();\n' +
'  cy.batch(function() {\n' +
'    var src = edge.source();\n' +
'    var tgt = edge.target();\n' +
'    edge.addClass("edge-focus");\n' +
'    src.addClass("edge-context");\n' +
'    tgt.addClass("edge-context");\n' +
'    cy.nodes().not(src).not(tgt).addClass("node-muted");\n' +
'    cy.edges().not(edge).addClass("edge-muted");\n' +
'  });\n' +
'  closePanel();\n' +
'});\n' +
'cy.on("tap", function(e) { if (e.target === cy) { clearEdgeFocus(); closePanel(); } });\n' +
'function clearEdgeFocus() { cy.batch(function() { cy.elements().removeClass("node-muted edge-context edge-muted edge-focus"); }); }\n' +
'function getLayout(name) {\n' +
'  if (name === "cose-bilkent") name = "cose";\n' +
'  var layouts = {\n' +
'    "cose": { name: "cose", animate: false, fit: true, padding: 64, nodeDimensionsIncludeLabels: true, nodeRepulsion: function() { return 9000; }, idealEdgeLength: function() { return 180; }, edgeElasticity: function() { return 0.35; }, gravity: 0.5, numIter: 300, randomize: false },\n' +
'    "concentric": { name: "concentric", animate: false, fit: true, padding: 64, concentric: function(n) { return n.degree(); }, levelWidth: function() { return 1; } },\n' +
'    "breadthfirst": { name: "breadthfirst", animate: false, fit: true, padding: 64, directed: true }\n' +
'  };\n' +
'  return layouts[name] || layouts["cose"];\n' +
'}\n' +
'function changeLayout(name) {\n' +
'  document.querySelectorAll(".btn").forEach(function(b) { b.classList.remove("active"); });\n' +
'  event.target.classList.add("active");\n' +
'  cy.layout(getLayout(name)).run();\n' +
'}\n' +
'var searchTimer = null;\n' +
'function handleSearch(val) {\n' +
'  clearTimeout(searchTimer);\n' +
'  searchTimer = setTimeout(function() {\n' +
'    var q = val.toLowerCase().trim();\n' +
'    cy.batch(function() {\n' +
'      cy.elements().removeClass("dimmed matched");\n' +
'      if (!q) return;\n' +
'      cy.nodes().forEach(function(n) {\n' +
'        var match = (n.data("label") || "").toLowerCase().includes(q) || (n.data("definition") || "").toLowerCase().includes(q);\n' +
'        n.addClass(match ? "matched" : "dimmed");\n' +
'      });\n' +
'      cy.edges().forEach(function(e) {\n' +
'        e.addClass(e.source().hasClass("matched") && e.target().hasClass("matched") ? "matched" : "dimmed");\n' +
'      });\n' +
'    });\n' +
'  }, 200);\n' +
'}\n' +
'function showPanel(data) {\n' +
'  document.getElementById("panel-name").textContent = data.label || "";\n' +
'  document.getElementById("panel-category").textContent = data.category || "";\n' +
'  document.getElementById("panel-definition").textContent = data.definition || "";\n' +
'  var aliases = data.aliases || [];\n' +
'  var aliasSection = document.getElementById("panel-aliases-section");\n' +
'  if (aliases.length) { aliasSection.style.display = ""; document.getElementById("panel-aliases").textContent = aliases.join(", "); }\n' +
'  else { aliasSection.style.display = "none"; }\n' +
'  var src = "《" + (data.textbook_name || "") + "》";\n' +
'  if (data.chapter_title) src += "\\n" + data.chapter_title;\n' +
'  if (data.page_number) src += " · 第 " + data.page_number + " 页";\n' +
'  document.getElementById("panel-source").textContent = src;\n' +
'  document.getElementById("panel").classList.add("show");\n' +
'}\n' +
'function closePanel() { document.getElementById("panel").classList.remove("show"); }\n' +
'</' + 'script>\n' +
'</div>\n' +
'</body>\n</html>';
}

watch(() => props.graphData,
  (newGraphData, oldGraphData) => {
    if (!newGraphData) return;
    if (cy.value && oldGraphData) {
      refreshGraphElements();
      applySearch(searchQuery.value.toLowerCase().trim());
    }
  }
);

watchEffect(() => {
  const hasData = props.graphData && Array.isArray(props.graphData.nodes) && props.graphData.nodes.length > 0;
  const noProgress = !props.buildProgress;
  if (hasData && noProgress && !cy.value) {
    nextTick(() => {
      if (!cy.value) initCytoscape();
    });
  }
});

onMounted(() => {
  if (props.graphData && !props.buildProgress) {
    nextTick(() => initCytoscape());
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

.graph-legend {
  position: absolute;
  top: 62px;
  left: 12px;
  background: var(--bg-card, #1e293b);
  border: 1px solid var(--border, #334155);
  border-radius: var(--radius-md, 8px);
  padding: 10px 14px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  font-size: 12px;
  color: var(--text-secondary, #cbd5e1);
  white-space: nowrap;
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

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  width: 260px;
}

.progress-bar-track {
  flex: 1;
  height: 8px;
  background: var(--border, #334155);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-bar-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #94a3b8);
  min-width: 48px;
  text-align: right;
}
</style>
