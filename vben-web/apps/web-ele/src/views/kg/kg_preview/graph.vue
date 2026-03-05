<script lang="ts" setup>
import type {
  ForceGraph3DInstance,
  LinkObject,
  NodeObject,
} from '3d-force-graph';

import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import ForceGraph3D from '3d-force-graph';
import { ElMessage } from 'element-plus';
import * as THREE from 'three';
import SpriteText from 'three-spritetext';

import { nodeStyleDefinitions } from './style.vue';

const props = withDefaults(
  defineProps<{
    autoRotate?: boolean;
    graphLimit?: number;
    nodeSize?: number;
    nodeStyle?: string;
    searchKeyword?: string;
    selectedCategory?: string;
    selectedDatabase?: string;
    showEdges?: boolean;
    showLabels?: boolean;
  }>(),
  {
    searchKeyword: '',
    selectedCategory: '',
    selectedDatabase: '',
    graphLimit: 300,
    showLabels: true,
    showEdges: true,
    nodeSize: 1,
    autoRotate: true,
    nodeStyle: 'style1',
  },
);

// Pipe Shader Definitions
const pipeVertexShader = `
varying vec2 vUv;
void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const pipeFragmentShader = `
uniform vec3 color;
uniform float progress;
varying vec2 vUv;
void main() {
    // vUv.y goes from 0 to 1 along the height of the cylinder
    // We want to fill from one end (0) to the other (1).
    if (vUv.y > progress) {
        discard;
    }
    // Simple shading
    gl_FragColor = vec4(color, 0.8); 
}
`;

// Use the imported THREE instance
let threeLib: any = THREE;
const threeImportPromise: Promise<any> = Promise.resolve(THREE);
let particleSystem: any = null;
let particleAnimationId: null | number = null;
let particleSetupScheduled = false;
let particleAutoRotateActive = true;
let currentAnimationId = 0;
let graphLimitFetchTimer: null | ReturnType<typeof setTimeout> = null;

// 图谱数据缓存（使用 sessionStorage）
const GRAPH_CACHE_KEY = 'kg_graph_cache';
const GRAPH_CACHE_EXPIRY = 5 * 60 * 1000; // 5 分钟缓存有效期

interface GraphCacheEntry {
  data: VisualizerData;
  database: string | undefined;
  limit: number;
  timestamp: number;
}

function hasGraphContent(data: null | VisualizerData | undefined): boolean {
  if (!data) return false;
  return (data.nodes?.length ?? 0) > 0 || (data.edges?.length ?? 0) > 0;
}

function getGraphCache(
  database: string | undefined,
  limit: number,
): null | VisualizerData {
  try {
    const cached = sessionStorage.getItem(GRAPH_CACHE_KEY);
    if (!cached) return null;

    const entry: GraphCacheEntry = JSON.parse(cached);
    const now = Date.now();

    // 检查是否过期
    if (now - entry.timestamp > GRAPH_CACHE_EXPIRY) {
      sessionStorage.removeItem(GRAPH_CACHE_KEY);
      return null;
    }

    // 检查 database 与 limit 是否匹配
    if (entry.database !== database || entry.limit !== limit) {
      return null;
    }

    if (!hasGraphContent(entry.data)) {
      sessionStorage.removeItem(GRAPH_CACHE_KEY);
      return null;
    }

    console.warn('[Graph Cache] 命中缓存，跳过网络请求');
    return entry.data;
  } catch (error) {
    console.warn('[Graph Cache] 读取缓存失败:', error);
    return null;
  }
}

function setGraphCache(
  data: VisualizerData,
  database: string | undefined,
  limit: number,
): void {
  try {
    if (!hasGraphContent(data)) {
      return;
    }
    const entry: GraphCacheEntry = {
      data,
      database,
      limit,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(GRAPH_CACHE_KEY, JSON.stringify(entry));
    console.warn('[Graph Cache] 数据已缓存');
  } catch (error) {
    console.warn('[Graph Cache] 写入缓存失败:', error);
  }
}

function clearGraphCache(): void {
  sessionStorage.removeItem(GRAPH_CACHE_KEY);
  console.warn('[Graph Cache] 缓存已清除');
}

// 高亮状态
const highlightedNodeIds = shallowRef<Set<string>>(new Set());
const highlightedLinkIds = shallowRef<Set<string>>(new Set());
const isHighlightActive = computed(
  () => highlightedNodeIds.value.size > 0 || highlightedLinkIds.value.size > 0,
);

// 高亮时保存的原始位置（用于恢复）
const originalNodePositions = shallowRef<
  Map<string, { x: number; y: number; z: number }>
>(new Map());
const isAnimating = ref(false);

function ensureThree() {
  return threeLib;
}

interface GraphNode extends NodeObject {
  id: string;
  label: string;
  value: number;
  category: string;
}

interface GraphEdge extends LinkObject<GraphNode> {
  source: string;
  target: string;
  label: string;
  description?: string;
  value: number;
  properties?: Record<string, any>;
}

interface VisualizerData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

function fallbackNormalizeGraph(rawNodes: unknown[], rawEdges: unknown[]): VisualizerData {
  const nodes: GraphNode[] = (Array.isArray(rawNodes) ? rawNodes : [])
    .map((item: any, index) => {
      const id = String(item?.id ?? item?.neo_id ?? item?.elementId ?? `node-${index}`);
      const label = String(item?.label ?? item?.name ?? id);
      const category = String(item?.category ?? item?.type ?? 'DEFAULT').toUpperCase();
      const value = Number(item?.value ?? item?.weight ?? 1) || 1;
      return { id, label, category, value } as GraphNode;
    })
    .filter((node) => Boolean(node.id));

  const nodeIdSet = new Set(nodes.map((n) => n.id));

  const edges: GraphEdge[] = (Array.isArray(rawEdges) ? rawEdges : [])
    .map((item: any) => {
      const source = String(item?.source ?? item?.from ?? item?.start ?? '');
      const target = String(item?.target ?? item?.to ?? item?.end ?? '');
      const label = String(item?.label ?? item?.type ?? 'RELATED_TO');
      const value = Number(item?.value ?? item?.weight ?? 1) || 1;
      return { source, target, label, value } as GraphEdge;
    })
    .filter((edge) => {
      if (!edge.source || !edge.target) return false;
      return nodeIdSet.has(edge.source) && nodeIdSet.has(edge.target);
    });

  return { nodes, edges };
}

function toPlainObject(value: unknown): null | Record<string, any> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, any>;
  }
  return null;
}

function pickFromContainers(
  source: Record<string, any>,
  keys: string[],
): unknown {
  for (const key of keys) {
    if (key in source && source[key] !== undefined && source[key] !== null) {
      return source[key];
    }
    const lowerKey = key.toLowerCase();
    if (
      lowerKey in source &&
      source[lowerKey] !== undefined &&
      source[lowerKey] !== null
    ) {
      return source[lowerKey];
    }
    const upperKey = key.toUpperCase();
    if (
      upperKey in source &&
      source[upperKey] !== undefined &&
      source[upperKey] !== null
    ) {
      return source[upperKey];
    }
  }
  for (const containerKey of ['properties', 'props', 'attributes', 'data']) {
    const container = toPlainObject(source[containerKey]);
    if (!container) continue;
    const candidate = pickFromContainers(container, keys);
    if (candidate !== undefined) {
      return candidate;
    }
  }
  return undefined;
}

function resolveNodeId(
  rawNode: Record<string, any>,
  fallbackIndex: number,
): string {
  const idCandidate = pickFromContainers(rawNode, [
    'id',
    'neo_id',
    'neoId',
    'elementId',
    'ID',
    'Id',
    'identity',
    'uuid',
    'nodeId',
  ]);
  if (typeof idCandidate === 'string' && idCandidate.trim() !== '') {
    return idCandidate;
  }
  if (typeof idCandidate === 'number') {
    return String(idCandidate);
  }
  return `node-${fallbackIndex}`;
}

function resolveNodeLabel(
  rawNode: Record<string, any>,
  fallbackId: string,
): string {
  const labelCandidate = pickFromContainers(rawNode, [
    'label',
    'name',
    'title',
    'text',
  ]);
  if (typeof labelCandidate === 'string' && labelCandidate.trim() !== '') {
    return labelCandidate;
  }
  return fallbackId;
}

function resolveNodeCategory(rawNode: Record<string, any>): string {
  // 优先从 properties.type 获取（这是 Neo4j 实体的真实类型）
  const props = rawNode.properties || rawNode.props || rawNode.data;
  if (props && typeof props === 'object') {
    const typeValue = props.type || props.category || props.kind;
    if (typeof typeValue === 'string' && typeValue.trim() !== '') {
      return typeValue.toUpperCase();
    }
  }

  // 其次尝试直接属性
  const directType = rawNode.type || rawNode.kind;
  if (
    typeof directType === 'string' &&
    directType.trim() !== '' &&
    directType !== 'Entity'
  ) {
    return directType.toUpperCase();
  }

  // 再尝试 category（但过滤掉 'Entity' 这种通用标签）
  const category = rawNode.category;
  if (
    typeof category === 'string' &&
    category.trim() !== '' &&
    category !== 'Entity'
  ) {
    return category.toUpperCase();
  }

  // 最后尝试 labels
  if (Array.isArray(rawNode.labels) && rawNode.labels.length > 0) {
    // 过滤掉通用标签
    const specificLabels = rawNode.labels.filter(
      (l: string) => !['Chunk', 'Document', 'Entity', 'Node'].includes(l),
    );
    if (specificLabels.length > 0) {
      return String(specificLabels[0]).toUpperCase();
    }
  }

  return 'DEFAULT';
}

function resolveNumeric(value: unknown, defaultValue = 1): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return defaultValue;
}

function resolveEndpoint(
  edge: Record<string, any>,
  keyCandidates: string[],
): null | string {
  const directCandidate = pickFromContainers(edge, keyCandidates);
  let endpointCandidate = directCandidate;
  if (typeof endpointCandidate === 'object' && endpointCandidate !== null) {
    const endpointObj = toPlainObject(endpointCandidate);
    if (endpointObj) {
      const nestedId = pickFromContainers(endpointObj, [
        'id',
        'neo_id',
        'neoId',
        'elementId',
        'ID',
        'Id',
        'identity',
        'uuid',
        'nodeId',
      ]);
      if (typeof nestedId === 'string' && nestedId.trim() !== '') {
        endpointCandidate = nestedId;
      } else if (typeof nestedId === 'number') {
        endpointCandidate = String(nestedId);
      }
    }
  }
  if (
    typeof endpointCandidate === 'string' &&
    endpointCandidate.trim() !== ''
  ) {
    return endpointCandidate;
  }
  if (typeof endpointCandidate === 'number') {
    return String(endpointCandidate);
  }
  return null;
}

function ensureNodeExists(nodeMap: Map<string, GraphNode>, nodeId: string) {
  if (!nodeMap.has(nodeId)) {
    nodeMap.set(nodeId, {
      id: nodeId,
      label: nodeId,
      value: 1,
      category: 'DEFAULT',
    });
  }
}

function normalizeBackendGraph(
  rawNodes: unknown[],
  rawEdges: unknown[],
): VisualizerData {
  const nodeMap = new Map<string, GraphNode>();
  const discoveredIds = new Set<string>();
  rawNodes.forEach((rawNode, index) => {
    const nodeObj = toPlainObject(rawNode);
    if (!nodeObj) return;
    const id = resolveNodeId(nodeObj, index);
    const label = resolveNodeLabel(nodeObj, id);
    const value = resolveNumeric(
      pickFromContainers(nodeObj, ['value', 'weight', 'score', 'size']),
      1,
    );
    const category = resolveNodeCategory(nodeObj);
    nodeMap.set(id, {
      id,
      label,
      value,
      category,
    });
    discoveredIds.add(id);
  });

  const edges: GraphEdge[] = [];
  rawEdges.forEach((rawEdge) => {
    const edgeObj = toPlainObject(rawEdge);
    if (!edgeObj) return;
    const source = resolveEndpoint(edgeObj, [
      'source',
      'from',
      'start',
      'startNode',
      'sourceId',
      'fromId',
    ]);
    const target = resolveEndpoint(edgeObj, [
      'target',
      'to',
      'end',
      'endNode',
      'targetId',
      'toId',
    ]);
    if (!source || !target) return;
    discoveredIds.add(source);
    discoveredIds.add(target);
    ensureNodeExists(nodeMap, source);
    ensureNodeExists(nodeMap, target);
    const labelCandidate = pickFromContainers(edgeObj, [
      'label',
      'name',
      'type',
      'relationship',
      'rel',
    ]);
    let label =
      typeof labelCandidate === 'string' && labelCandidate.trim() !== ''
        ? labelCandidate
        : `${source} → ${target}`;

    // 尝试汉化
    const mappedLabel = relationMap.value[label];
    if (mappedLabel) {
      label = mappedLabel;
    }

    const value = resolveNumeric(
      pickFromContainers(edgeObj, [
        'value',
        'weight',
        'score',
        'size',
        'count',
      ]),
      1,
    );

    // 提取属性
    const properties =
      edgeObj.properties || edgeObj.props || edgeObj.data || {};

    // 提取 description（优先从 properties 中获取，也可能在顶层）
    const description =
      edgeObj.description || properties.description || properties.desc || '';

    edges.push({
      source,
      target,
      label: description || label, // 优先显示 description
      description,
      value,
      properties,
    });
  });

  const normalizedNodes = [...nodeMap.values()];
  const filteredEdges = edges.filter(
    (edge) =>
      nodeMap.has(String(edge.source)) && nodeMap.has(String(edge.target)),
  );
  if (filteredEdges.length === 0 && edges.length > 0) {
    return {
      nodes: normalizedNodes,
      edges,
    };
  }
  return {
    nodes: normalizedNodes,
    edges: filteredEdges,
  };
}

particleAutoRotateActive = props.autoRotate;

function setupParticleBackground() {
  if (!graphInstance) return;
  const THREE: any = ensureThree();
  if (!THREE) {
    if (!particleSetupScheduled && threeImportPromise) {
      particleSetupScheduled = true;
      threeImportPromise
        .then((resolved) => {
          particleSetupScheduled = false;
          if (resolved && graphInstance) {
            setupParticleBackground();
          }
        })
        .catch(() => {
          particleSetupScheduled = false;
        });
    }
    return;
  }
  particleSetupScheduled = false;
  const scene = (graphInstance.scene?.() ?? null) as null | Record<string, any>;
  if (!scene) return;
  disposeParticleBackground();
  const geometry = new THREE.BufferGeometry();
  const vertices: number[] = [];
  const spread = 2700;
  // TODO 调整密度
  const count = 9000;
  for (let i = 0; i < count; i++) {
    const x =
      (Math.random() * spread + Math.random() * spread) * 0.5 - spread * 0.5;
    const y =
      (Math.random() * spread + Math.random() * spread) * 0.5 - spread * 0.5;
    const z =
      (Math.random() * spread + Math.random() * spread) * 0.5 - spread * 0.5;
    vertices.push(x, y, z);
  }
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(vertices, 3),
  );
  const material = new THREE.PointsMaterial({
    size: 1.6,
    color: new THREE.Color('#cbd5f5'),
    transparent: true,
    opacity: 0.65,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const particles = new THREE.Points(geometry, material);
  particles.name = 'kg-background-particles';
  particles.renderOrder = -1;
  particleSystem = particles;
  particleAutoRotateActive = props.autoRotate;
  scene.add(particles);
  startParticleAnimation();
}

function startParticleAnimation() {
  stopParticleAnimation();
  if (!particleSystem) return;
  const animate = () => {
    if (!particleSystem) return;
    const factor = particleAutoRotateActive ? 1 : 0;
    particleSystem.rotation.x += 0.0005 * factor;
    particleSystem.rotation.y += 0.0008 * factor;
    const controls = graphInstance?.controls?.() as
      | undefined
      | { autoRotate?: boolean; update?: () => void };
    if (controls?.autoRotate) {
      controls.update?.();
    }
    particleAnimationId = requestAnimationFrame(animate);
  };
  particleAnimationId = requestAnimationFrame(animate);
}

function stopParticleAnimation() {
  if (particleAnimationId !== null) {
    cancelAnimationFrame(particleAnimationId);
    particleAnimationId = null;
  }
}

function disposeParticleBackground() {
  stopParticleAnimation();
  if (!graphInstance || !particleSystem) {
    particleSystem = null;
    return;
  }
  const scene = graphInstance.scene?.();
  if (scene) {
    scene.remove(particleSystem);
  }
  particleSystem.geometry?.dispose?.();
  particleSystem.material?.dispose?.();
  particleSystem = null;
}

function updateParticleAutoRotate(enabled: boolean) {
  particleAutoRotateActive = enabled;
}
const loading = ref(false);
const graphData = shallowRef<VisualizerData>({ nodes: [], edges: [] });
const containerRef = ref<HTMLDivElement | null>(null);
let graphInstance: ForceGraph3DInstance | null = null;

// 定义更多类别颜色
const categoryColors: Record<string, string> = {
  // 人物相关
  PERSON: '#4e9af1',
  人物: '#4e9af1',
  角色: '#4e9af1',
  CHARACTER: '#4e9af1',

  // 组织相关
  ORGANIZATION: '#f38b3f',
  组织: '#f38b3f',
  机构: '#f38b3f',
  公司: '#f38b3f',
  ORG: '#f38b3f',

  // 地点相关
  LOCATION: '#4caf50',
  地点: '#4caf50',
  地名: '#4caf50',
  PLACE: '#4caf50',
  GEO: '#4caf50',

  // 产品相关
  PRODUCT: '#9b59b6',
  产品: '#9b59b6',
  物品: '#9b59b6',
  ITEM: '#9b59b6',
  OBJECT: '#9b59b6',

  // 概念相关
  CONCEPT: '#1abc9c',
  概念: '#1abc9c',
  IDEA: '#1abc9c',

  // 事件相关
  EVENT: '#e74c3c',
  事件: '#e74c3c',

  // 时间相关
  TIME: '#f39c12',
  时间: '#f39c12',
  DATE: '#f39c12',

  // 默认/未知
  DEFAULT: '#95a5a6',
  UNKNOWN: '#95a5a6',
  ENTITY: '#7f8c8d',
};

// 为未知类别生成稳定的颜色
function hashStringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (str.codePointAt(i) ?? 0) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 65%, 55%)`;
}

const relationMap = ref<Record<string, string>>({});

const filteredGraph = computed<{ edges: GraphEdge[]; nodes: GraphNode[] }>(
  () => {
    const keyword = props.searchKeyword.trim().toLowerCase();
    const nodes = graphData.value.nodes.filter((node: GraphNode) => {
      const matchesKeyword =
        keyword === '' || node.label.toLowerCase().includes(keyword);
      const matchesCategory =
        props.selectedCategory === '' ||
        node.category === props.selectedCategory;
      return matchesKeyword && matchesCategory;
    });

    const visibleIds = new Set(nodes.map((node: GraphNode) => node.id));
    const edges = props.showEdges
      ? graphData.value.edges.filter(
          (edge: GraphEdge) =>
            visibleIds.has(edge.source) && visibleIds.has(edge.target),
        )
      : [];

    return { nodes, edges };
  },
);

function getCategoryColor(category: string): string {
  if (!category) return categoryColors.DEFAULT || '#95a5a6';
  const upperCategory = category.toUpperCase();
  // 先查预定义颜色
  if (categoryColors[upperCategory]) {
    return categoryColors[upperCategory];
  }
  // 原始大小写也查一下
  if (categoryColors[category]) {
    return categoryColors[category];
  }
  // 未知类别生成稳定颜色
  return hashStringToColor(upperCategory);
}

function getNodeColor(node: GraphNode): string {
  const baseColor = getCategoryColor(node.category);
  return baseColor; // 始终保持原色，仅通过透明度区分
}

function getNodeOpacity(_node: GraphNode): number {
  if (!isHighlightActive.value) return 1;
  // 高亮模式下，默认所有节点透明度为 0.1 (暗淡)
  // 具体的动画效果由 highlightElements 中的 requestAnimationFrame 直接操作 ThreeJS 对象来实现
  // 这样可以避免 Vue 响应式系统的性能开销
  return 0.1;
}

function getLinkColor(link: GraphEdge): string {
  if (!isHighlightActive.value) return 'rgba(102,128,255,0.6)';

  // 检查两端节点是否都被高亮，如果不是则完全隐藏这条边
  const sourceId =
    typeof link.source === 'object' ? (link.source as any).id : link.source;
  const targetId =
    typeof link.target === 'object' ? (link.target as any).id : link.target;

  const sourceHighlighted = highlightedNodeIds.value.has(sourceId);
  const targetHighlighted = highlightedNodeIds.value.has(targetId);

  if (!sourceHighlighted || !targetHighlighted) {
    return 'rgba(0,0,0,0)'; // 完全透明
  }

  // 高亮模式下，默认连线透明度为 0 (不可见)，等待动画过渡到 0.8
  return 'rgba(102, 128, 255, 0)';
}

function getLinkWidth(link: GraphEdge): number {
  const baseWidth = Math.max((link.value ?? 1) * 0.45, 1.2);
  if (!isHighlightActive.value) return baseWidth;
  // 生成连线的匹配 ID
  const sourceId =
    typeof link.source === 'object' ? (link.source as any).id : link.source;
  const targetId =
    typeof link.target === 'object' ? (link.target as any).id : link.target;

  // 检查两端节点是否都被高亮，如果不是则宽度为0
  const sourceHighlighted = highlightedNodeIds.value.has(sourceId);
  const targetHighlighted = highlightedNodeIds.value.has(targetId);
  if (!sourceHighlighted || !targetHighlighted) {
    return 0;
  }

  const linkKey = `${sourceId}-${targetId}`;
  const linkKeyReverse = `${targetId}-${sourceId}`;
  const isHighlighted =
    highlightedLinkIds.value.has(linkKey) ||
    highlightedLinkIds.value.has(linkKeyReverse);
  return isHighlighted ? baseWidth * 2.5 : baseWidth * 0.5;
}

function shouldUseDemoData(): boolean {
  // 将返回值切换为 true 使用内置演示数据，设为 false 则请求 Neo4j 后端
  return false;
}

function resolveNodeRenderer(styleKey: string) {
  const renderer = nodeStyleDefinitions[styleKey];
  if (renderer) return renderer;
  return nodeStyleDefinitions.style1 ?? Object.values(nodeStyleDefinitions)[0];
}

function createNodeObject(node: GraphNode): any {
  const THREE = ensureThree();
  if (!THREE) {
    return new SpriteText(node.label);
  }

  // 移除降级逻辑，保持高亮模式下节点样式与默认模式一致
  // 仅通过透明度区分高亮与非高亮

  const renderer = resolveNodeRenderer(props.nodeStyle);
  const rendered = renderer?.({
    THREE,
    node,
    getCategoryColor,
    nodeSize: props.nodeSize,
    showLabels: props.showLabels,
  });
  if (rendered) return rendered;
  const fallbackLabel = new SpriteText(node.label);
  fallbackLabel.color = getCategoryColor(node.category);
  return fallbackLabel;
}

function updateGraphData() {
  if (!graphInstance) return;
  const { nodes, edges } = filteredGraph.value;
  const nodeCopies = nodes.map((node: GraphNode) => ({ ...node }));
  const linkCopies = edges.map((edge: GraphEdge) => ({ ...edge }));
  graphInstance.graphData({ nodes: nodeCopies, links: linkCopies });
  refreshNodeAppearance();
  refreshLinkAppearance();
}

function refreshNodeAppearance() {
  if (!graphInstance) return;
  graphInstance.nodeThreeObject((node: NodeObject) =>
    createNodeObject(node as GraphNode),
  );
  graphInstance.nodeThreeObjectExtend(false);
  graphInstance.refresh();
}

let globalPipeGeometry: any = null;
let globalPipeMaterial: any = null;

function refreshLinkAppearance() {
  if (!graphInstance) return;

  if (!globalPipeGeometry) {
    globalPipeGeometry = new threeLib.CylinderGeometry(0.5, 0.5, 1, 8, 1, true);
    globalPipeGeometry.translate(0, 0.5, 0);
    globalPipeGeometry.rotateX(Math.PI / 2);
  }
  if (!globalPipeMaterial) {
    globalPipeMaterial = new threeLib.ShaderMaterial({
      uniforms: {
        color: { value: new threeLib.Color('#6680ff') },
        progress: { value: 0 },
      },
      vertexShader: pipeVertexShader,
      fragmentShader: pipeFragmentShader,
      transparent: true,
      side: threeLib.DoubleSide,
      depthWrite: false,
      blending: threeLib.AdditiveBlending,
    });
  }

  graphInstance.linkThreeObject((link: any) => {
    const group = new threeLib.Group();
    // Initially not highlighted, effectively invisible
    const material = globalPipeMaterial.clone();
    material.uniforms = {
      color: { value: new threeLib.Color('#6680ff') },
      progress: { value: 0 },
    };

    const pipe = new threeLib.Mesh(globalPipeGeometry, material);
    pipe.userData = { isPipe: true };
    pipe.visible = false; // keep draw calls to minimum
    group.add(pipe);

    const textValue = link.description || link.label || '';
    if (textValue) {
      const sprite = new SpriteText(textValue) as any;
      sprite.color = '#ffffff';
      sprite.textHeight = 4;
      sprite.backgroundColor = 'rgba(14, 116, 144, 0.85)';
      sprite.padding = 1.5;
      sprite.borderRadius = 2;
      sprite.userData = { isLabel: true };
      sprite.visible = false;
      group.add(sprite);
    }

    return group;
  });

  graphInstance.linkThreeObjectExtend(true);
  graphInstance.linkPositionUpdate((obj: any, { start, end }: any) => {
    if (!obj) return;
    const startV = new threeLib.Vector3(start.x, start.y, start.z);
    const endV = new threeLib.Vector3(end.x, end.y, end.z);
    const dist = startV.distanceTo(endV);

    if (obj.children) {
      obj.children.forEach((child: any) => {
        if (child.userData?.isPipe) {
          child.position.copy(startV);
          child.lookAt(endV);
          child.scale.set(1, 1, dist);
        } else if (child.userData?.isLabel) {
          child.position.copy(startV).lerp(endV, 0.5);
        }
      });
    }
  });
}

function applyLinkStyles() {
  if (!graphInstance) return;
  graphInstance.linkOpacity(isHighlightActive.value ? 0.1 : 0.45);
  graphInstance.linkWidth((link) => getLinkWidth(link as GraphEdge));
  graphInstance.linkColor((link) => getLinkColor(link as GraphEdge));
  graphInstance.linkDirectionalParticles(props.showEdges ? 2 : 0);
  graphInstance.linkDirectionalParticleWidth(2.4);
  graphInstance.linkDirectionalParticleSpeed(() => 0.0035);
  graphInstance.linkDirectionalParticleColor(() => '#4ecdc4');
  graphInstance.refresh();
}

function applyForceSettings() {
  if (!graphInstance) return;
  const linkForce = graphInstance.d3Force('link') as any;
  if (linkForce?.distance) {
    linkForce.distance((link: GraphEdge) => 180 + (link.value ?? 1) * 18);
    linkForce.strength(0.75);
  }
  const chargeForce = graphInstance.d3Force('charge') as any;
  if (chargeForce?.strength) {
    chargeForce.strength(-240);
  }
  graphInstance.d3VelocityDecay(0.22);
}

function applyAutoRotate(enabled: boolean) {
  if (!graphInstance) return;
  const controls = graphInstance.controls?.() as
    | undefined
    | { autoRotate?: boolean; autoRotateSpeed?: number; update?: () => void };
  if (!controls) return;
  controls.autoRotate = enabled;
  controls.autoRotateSpeed = 0.8;
  controls.update?.();
}

function updateGraphSize() {
  if (!graphInstance || !containerRef.value) return;
  const { clientWidth, clientHeight } = containerRef.value;
  if (clientWidth === 0 || clientHeight === 0) return;
  graphInstance.width(clientWidth);
  graphInstance.height(clientHeight);
}

function initForceGraph() {
  if (!containerRef.value || graphInstance) return;
  const factory = ForceGraph3D as unknown as () => any;
  const instance = factory();
  instance(containerRef.value)
    .backgroundColor('#0b1220')
    .nodeId('id')
    .nodeLabel((node: GraphNode) => node.label)
    .nodeColor((node: GraphNode) => getNodeColor(node))
    .nodeOpacity((node: GraphNode) => getNodeOpacity(node))
    .linkLabel((link: GraphEdge) => {
      const desc = link.description || '';
      const source =
        typeof link.source === 'object'
          ? (link.source as any).label
          : link.source;
      const target =
        typeof link.target === 'object'
          ? (link.target as any).label
          : link.target;

      return `
				<div class="p-2 bg-gray-900/90 rounded border border-gray-700 shadow-xl backdrop-blur-sm text-xs">
					<div class="font-bold text-cyan-400 mb-1">${link.label}</div>
					${desc && desc !== link.label ? `<div class="text-gray-300 mb-1 max-w-[200px] whitespace-normal">${desc}</div>` : ''}
					<div class="text-gray-500 mt-1 pt-1 border-t border-gray-700/50 flex items-center gap-1">
						<span class="truncate max-w-[80px]">${source}</span>
						<span>→</span>
						<span class="truncate max-w-[80px]">${target}</span>
					</div>
				</div>
			`;
    })
    .linkOpacity(0.35)
    .linkColor((link: GraphEdge) => getLinkColor(link))
    .warmupTicks(60)
    .cooldownTicks(150)
    .onBackgroundClick(() => {
      // 点击背景取消高亮
      clearHighlight();
    });

  graphInstance = instance as ForceGraph3DInstance;
  threeLib =
    threeLib ?? (instance as any).THREE ?? (factory as any).THREE ?? null;
  refreshNodeAppearance();
  applyLinkStyles();
  applyForceSettings();
  applyAutoRotate(props.autoRotate);
  updateGraphSize();
  setupParticleBackground();
  window.addEventListener('resize', updateGraphSize);
}

async function fetchGraphData(useDemo = false, forceRefresh = false) {
  loading.value = true;
  try {
    if (!useDemo) {
      const effectiveLimit = Math.max(
        100,
        Math.min(5000, Number(props.graphLimit) || 300),
      );

      // 尝试从缓存获取数据（除非强制刷新）
      if (!forceRefresh) {
        const cachedData = getGraphCache(props.selectedDatabase, effectiveLimit);
        if (cachedData) {
          graphData.value = cachedData;
          updateGraphData();
          // 缓存命中时，缩短 loading 时间
          setTimeout(() => {
            loading.value = false;
          }, 200);
          return;
        }
      }

      // 构建带数据库参数的 URL
      const urlParams = new URLSearchParams({ limit: String(effectiveLimit) });
      if (props.selectedDatabase) {
        urlParams.append('database', props.selectedDatabase);
      }
      const endpointCandidates = ['/api/kg/visualize', '/kg/visualize'];
      let payload: any = null;
      let lastError: any = null;

      for (const endpoint of endpointCandidates) {
        try {
          const response = await fetch(`${endpoint}?${urlParams.toString()}`);
          if (!response.ok) {
            throw new Error(`请求失败: ${response.status}`);
          }
          payload = await response.json();
          lastError = null;
          break;
        } catch (error) {
          lastError = error;
        }
      }

      if (!payload) {
        throw lastError ?? new Error('图谱接口请求失败');
      }

      const data = payload?.data ?? {};
      const nodes = data?.nodes ?? data?.vertices ?? data?.entities ?? [];
      const edges = data?.edges ?? data?.links ?? data?.relations ?? data?.relationships ?? [];

      if (!(payload?.success && Array.isArray(nodes) && Array.isArray(edges))) {
        throw new Error(payload?.error || '图谱数据格式不正确');
      }

      let normalized = normalizeBackendGraph(nodes, edges);
      if (!hasGraphContent(normalized) && ((nodes?.length ?? 0) > 0 || (edges?.length ?? 0) > 0)) {
        normalized = fallbackNormalizeGraph(nodes, edges);
      }
      if (!hasGraphContent(normalized)) {
        throw new Error('后端返回空图数据');
      }
      graphData.value = normalized;
      setGraphCache(normalized, props.selectedDatabase, effectiveLimit);
      updateGraphData();
      return;
    }

    populateDemoData();
    updateGraphData();
  } catch (error) {
    if (!useDemo) {
      console.warn('获取知识图谱数据失败', error);
      const reason = error instanceof Error ? error.message : '未知错误';
      ElMessage.error(`图谱加载失败：${reason}`);
      return;
    }
    console.warn('获取演示数据失败', error);
  } finally {
    // 延迟关闭 loading，让图谱有时间渲染和布局，配合淡出动画实现丝滑过渡
    setTimeout(() => {
      loading.value = false;
    }, 600);
  }
}

function populateDemoData() {
  const nodes: GraphNode[] = [
    { id: 'node1', label: '张三', category: 'PERSON', value: 10 },
    { id: 'node2', label: '李四', category: 'PERSON', value: 8 },
    { id: 'node3', label: '王五', category: 'PERSON', value: 7 },
    { id: 'node4', label: '赵六', category: 'PERSON', value: 6 },
    { id: 'node5', label: '钱七', category: 'PERSON', value: 6 },

    { id: 'node6', label: '产品部', category: 'ORG', value: 9 },
    { id: 'node7', label: '研发部', category: 'ORG', value: 9 },
    { id: 'node8', label: '市场部', category: 'ORG', value: 8 },
    { id: 'node9', label: '数据平台组', category: 'ORG', value: 7 },
    { id: 'node10', label: '算法组', category: 'ORG', value: 7 },

    { id: 'node11', label: '北京', category: 'GEO', value: 6 },
    { id: 'node12', label: '上海', category: 'GEO', value: 6 },
    { id: 'node13', label: '深圳', category: 'GEO', value: 6 },

    { id: 'node14', label: '知识中台', category: 'PRODUCT', value: 8 },
    { id: 'node15', label: '搜索服务', category: 'PRODUCT', value: 7 },
    { id: 'node16', label: '推荐引擎', category: 'PRODUCT', value: 6 },

    { id: 'node17', label: '知识图谱', category: 'CONCEPT', value: 7 },
    { id: 'node18', label: '图数据库', category: 'CONCEPT', value: 7 },
    { id: 'node19', label: '向量检索', category: 'CONCEPT', value: 6 },
    { id: 'node20', label: '实体对齐', category: 'CONCEPT', value: 6 },
    { id: 'node21', label: 'RAG', category: 'CONCEPT', value: 6 },
    { id: 'node22', label: '数据治理', category: 'CONCEPT', value: 6 },

    { id: 'node23', label: '需求评审', category: 'EVENT', value: 5 },
    { id: 'node24', label: '上线发布', category: 'EVENT', value: 5 },
    { id: 'node25', label: '监控告警', category: 'EVENT', value: 5 },
    { id: 'node26', label: '回归测试', category: 'EVENT', value: 5 },

    { id: 'node27', label: '项目A', category: 'PRODUCT', value: 7 },
    { id: 'node28', label: '项目B', category: 'PRODUCT', value: 7 },
    { id: 'node29', label: '项目C', category: 'PRODUCT', value: 6 },

    { id: 'node30', label: '2026Q1', category: 'TIME', value: 4 },
  ];

  const edges: GraphEdge[] = [
    { source: 'node1', target: 'node6', label: '隶属', value: 3 },
    { source: 'node2', target: 'node7', label: '隶属', value: 3 },
    { source: 'node3', target: 'node7', label: '隶属', value: 2 },
    { source: 'node4', target: 'node9', label: '隶属', value: 2 },
    { source: 'node5', target: 'node10', label: '隶属', value: 2 },

    { source: 'node6', target: 'node23', label: '负责', value: 2 },
    { source: 'node7', target: 'node26', label: '负责', value: 2 },
    { source: 'node8', target: 'node24', label: '推动', value: 2 },
    { source: 'node9', target: 'node25', label: '建设', value: 2 },
    { source: 'node10', target: 'node16', label: '维护', value: 2 },

    { source: 'node1', target: 'node2', label: '合作', value: 2 },
    { source: 'node2', target: 'node3', label: '导师', value: 1 },
    { source: 'node3', target: 'node4', label: '评审', value: 1 },
    { source: 'node4', target: 'node5', label: '对接', value: 1 },
    { source: 'node5', target: 'node1', label: '反馈', value: 1 },

    { source: 'node6', target: 'node14', label: '规划', value: 3 },
    { source: 'node7', target: 'node14', label: '研发', value: 3 },
    { source: 'node8', target: 'node14', label: '推广', value: 2 },

    { source: 'node7', target: 'node15', label: '研发', value: 2 },
    { source: 'node9', target: 'node15', label: '提供数据', value: 2 },
    { source: 'node10', target: 'node15', label: '调优', value: 2 },

    { source: 'node10', target: 'node21', label: '落地', value: 2 },
    { source: 'node9', target: 'node19', label: '接入', value: 2 },
    { source: 'node7', target: 'node18', label: '选型', value: 2 },
    { source: 'node14', target: 'node17', label: '包含', value: 2 },
    { source: 'node17', target: 'node18', label: '依赖', value: 2 },
    { source: 'node15', target: 'node19', label: '依赖', value: 2 },
    { source: 'node21', target: 'node19', label: '使用', value: 2 },
    { source: 'node21', target: 'node17', label: '增强', value: 2 },
    { source: 'node20', target: 'node17', label: '提升质量', value: 1 },
    { source: 'node22', target: 'node17', label: '约束', value: 1 },

    { source: 'node11', target: 'node6', label: '驻地', value: 1 },
    { source: 'node12', target: 'node7', label: '驻地', value: 1 },
    { source: 'node13', target: 'node8', label: '驻地', value: 1 },
    { source: 'node11', target: 'node12', label: '协同', value: 1 },
    { source: 'node12', target: 'node13', label: '协同', value: 1 },

    { source: 'node23', target: 'node26', label: '前置', value: 1 },
    { source: 'node26', target: 'node24', label: '通过后', value: 1 },
    { source: 'node24', target: 'node25', label: '触发', value: 1 },
    { source: 'node25', target: 'node23', label: '反哺', value: 1 },

    { source: 'node27', target: 'node14', label: '子项目', value: 2 },
    { source: 'node28', target: 'node14', label: '子项目', value: 2 },
    { source: 'node29', target: 'node15', label: '子项目', value: 2 },
    { source: 'node27', target: 'node17', label: '构建', value: 2 },
    { source: 'node28', target: 'node21', label: '探索', value: 2 },
    { source: 'node29', target: 'node19', label: '集成', value: 2 },

    { source: 'node30', target: 'node23', label: '计划', value: 1 },
    { source: 'node30', target: 'node24', label: '里程碑', value: 1 },
    { source: 'node30', target: 'node22', label: '治理窗口', value: 1 },
    { source: 'node30', target: 'node14', label: '目标交付', value: 1 },
  ];

  graphData.value = { nodes, edges };
}

function handleReset() {
  if (!graphInstance) return;
  graphInstance.cameraPosition(
    { x: 0, y: 0, z: 600 },
    { x: 0, y: 0, z: 0 },
    1000,
  );
}

// 强制刷新图谱数据（清除缓存并重新获取）
function handleRefresh() {
  clearGraphCache();
  fetchGraphData(shouldUseDemoData(), true);
  ElMessage.success('正在刷新图谱数据...');
}

function handleDownload() {
  if (!graphInstance) return;
  const renderer = graphInstance.renderer();
  const canvas = renderer?.domElement;
  if (!canvas) return;
  const link = document.createElement('a');
  link.href = canvas.toDataURL('image/png');
  link.download = `knowledge-graph-${Date.now()}.png`;
  link.click();
}

watch(filteredGraph, () => updateGraphData());
watch(
  () => props.nodeSize,
  () => refreshNodeAppearance(),
);
watch(
  () => props.showLabels,
  () => refreshNodeAppearance(),
);
watch(
  () => props.autoRotate,
  (value) => {
    applyAutoRotate(value);
    updateParticleAutoRotate(value);
  },
);
watch(
  () => props.nodeStyle,
  () => refreshNodeAppearance(),
);
watch(
  () => props.showEdges,
  () => {
    updateGraphData();
    applyLinkStyles();
    refreshLinkAppearance();
  },
);
watch(
  () => [props.searchKeyword, props.selectedCategory],
  () => updateGraphData(),
);
// 数据库变化时重新获取数据
watch(
  () => props.selectedDatabase,
  () => fetchGraphData(shouldUseDemoData()),
);
watch(
  () => props.graphLimit,
  () => {
    if (graphLimitFetchTimer) {
      clearTimeout(graphLimitFetchTimer);
    }
    graphLimitFetchTimer = setTimeout(() => {
      fetchGraphData(shouldUseDemoData(), true);
      graphLimitFetchTimer = null;
    }, 250);
  },
);

onMounted(async () => {
  initForceGraph();
  if (!graphInstance) {
    ElMessage.error('3D 引擎初始化失败');
    return;
  }
  await fetchGraphData(shouldUseDemoData());
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateGraphSize);
  if (graphLimitFetchTimer) {
    clearTimeout(graphLimitFetchTimer);
    graphLimitFetchTimer = null;
  }
  disposeParticleBackground();
  if (graphInstance) {
    (graphInstance as unknown as { _destructor?: () => void })._destructor?.();
    graphInstance = null;
  }
});

function clearHighlight() {
  // 停止所有正在进行的动画
  currentAnimationId++;

  if (!graphInstance || isAnimating.value) return;

  // 如果有保存的原始位置，先恢复节点位置
  if (originalNodePositions.value.size > 0) {
    isAnimating.value = true;
    const { nodes } = graphInstance.graphData();

    // 动画恢复原始位置
    animateNodesToPositions(nodes, originalNodePositions.value, 400, () => {
      const currentGraph = graphInstance;
      if (!currentGraph) {
        isAnimating.value = false;
        return;
      }
      originalNodePositions.value.clear();
      highlightedNodeIds.value.clear();
      highlightedLinkIds.value.clear();

      // RESTORE Manually
      const { nodes, links } = currentGraph.graphData();
      nodes.forEach((n: any) => {
        if (!n.__threeObj) return;
        n.__threeObj.traverse((c: any) => {
          if (c.material) {
            c.material.opacity = 1;
            c.material.transparent = false;
            c.material.needsUpdate = true;
          }
        });
        const origScale = n.__threeObj.userData.originalScale;
        if (origScale) n.__threeObj.scale.copy(origScale);
      });
      links.forEach((l: any) => {
        if (!l.__threeObj) return;
        l.__threeObj.traverse((c: any) => {
          if (c.userData.isPipe || c.userData.isLabel) {
            c.visible = false;
          }
        });
      });

      applyLinkStyles();
      isAnimating.value = false;
    });
  } else {
    highlightedNodeIds.value.clear();
    highlightedLinkIds.value.clear();

    // RESTORE Manually
    const { nodes, links } = graphInstance.graphData();
    nodes.forEach((n: any) => {
      if (!n.__threeObj) return;
      n.__threeObj.traverse((c: any) => {
        if (c.material) {
          c.material.opacity = 1;
          c.material.transparent = false;
          c.material.needsUpdate = true;
        }
      });
      const origScale = n.__threeObj.userData.originalScale;
      if (origScale) n.__threeObj.scale.copy(origScale);
    });
    links.forEach((l: any) => {
      if (!l.__threeObj) return;
      l.__threeObj.traverse((c: any) => {
        if (c.userData.isPipe || c.userData.isLabel) {
          c.visible = false;
        }
      });
    });

    applyLinkStyles();
  }
}

// 动画过渡节点到目标位置
function animateNodesToPositions(
  nodes: any[],
  targetPositions: Map<string, { x: number; y: number; z: number }>,
  duration: number,
  onComplete?: () => void,
) {
  if (!graphInstance) return;

  const startTime = performance.now();
  const startPositions = new Map<string, { x: number; y: number; z: number }>();

  // 记录起始位置
  nodes.forEach((node: any) => {
    if (targetPositions.has(node.id)) {
      startPositions.set(node.id, {
        x: node.x || 0,
        y: node.y || 0,
        z: node.z || 0,
      });
    }
  });

  function animate() {
    const elapsed = performance.now() - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // 使用 easeOutCubic 缓动函数
    const eased = 1 - (1 - progress) ** 3;

    nodes.forEach((node: any) => {
      const start = startPositions.get(node.id);
      const target = targetPositions.get(node.id);
      if (start && target) {
        node.x = start.x + (target.x - start.x) * eased;
        node.y = start.y + (target.y - start.y) * eased;
        node.z = start.z + (target.z - start.z) * eased;
      }
    });

    graphInstance?.refresh();

    if (progress < 1) {
      requestAnimationFrame(animate);
    } else {
      onComplete?.();
    }
  }

  requestAnimationFrame(animate);
}

// 简单的力导向布局（用于高亮子图的紧凑排列）

// 缓动函数（ease-in-cubic）
function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3;
}

function highlightElements(nodeIds: string[], linkIds: string[]) {
  if (!graphInstance) return;

  // 1. 状态重置与初始化
  currentAnimationId++;
  const animationId = currentAnimationId;

  highlightedNodeIds.value = new Set(nodeIds);
  highlightedLinkIds.value = new Set(linkIds);

  applyLinkStyles();

  requestAnimationFrame(() => {
    if (currentAnimationId !== animationId) return;
    const currentGraph = graphInstance;
    if (!currentGraph) return;

    const { links, nodes } = currentGraph.graphData();
    const nodeMap = new Map(nodes.map((n: any) => [n.id, n]));

    nodes.forEach((n: any) => {
      if (!n.__threeObj) return;
      const obj = n.__threeObj;
      if (!highlightedNodeIds.value.has(n.id)) {
        if (obj.material) {
          obj.material.opacity = 0.1;
          obj.material.transparent = true;
        } else if (obj.children) {
          obj.traverse((c: any) => {
            if (c.material) {
              c.material.opacity = 0.1;
              c.material.transparent = true;
            }
          });
        }
      }
    });

    nodeIds.forEach((id) => {
      const node = nodeMap.get(id);
      if (node && node.__threeObj) {
        const obj = node.__threeObj;
        if (!obj.userData.originalScale) {
          obj.userData.originalScale = obj.scale.clone();
        }
        obj.scale.set(0.01, 0.01, 0.01);

        if (obj.material) {
          obj.material.opacity = 0.1;
          obj.material.transparent = true;
        } else if (obj.children) {
          obj.traverse((c: any) => {
            if (c.material) {
              c.material.opacity = 0.1;
              c.material.transparent = true;
            }
          });
        }
      }
    });

    const adjacency = new Map<
      string,
      Array<{ linkId: string; neighbor: string }>
    >();
    const subsetNodeSet = new Set(nodeIds);
    const subsetLinkSet = new Set(linkIds);
    const linkObjMap = new Map<string, any>();

    links.forEach((edge: any) => {
      const sourceId =
        typeof edge.source === 'object' ? edge.source.id : edge.source;
      const targetId =
        typeof edge.target === 'object' ? edge.target.id : edge.target;
      const linkKey = `${sourceId}-${targetId}`;
      const linkKeyReverse = `${targetId}-${sourceId}`;

      if (edge.__threeObj) {
        linkObjMap.set(linkKey, edge.__threeObj);
        linkObjMap.set(linkKeyReverse, edge.__threeObj);
      }

      if (
        (subsetLinkSet.has(linkKey) || subsetLinkSet.has(linkKeyReverse)) &&
        subsetNodeSet.has(sourceId) &&
        subsetNodeSet.has(targetId)
      ) {
        const validLinkId = subsetLinkSet.has(linkKey)
          ? linkKey
          : linkKeyReverse;

        if (!adjacency.has(sourceId)) adjacency.set(sourceId, []);
        if (!adjacency.has(targetId)) adjacency.set(targetId, []);

        adjacency
          .get(sourceId)
          ?.push({ neighbor: targetId, linkId: validLinkId });
        adjacency
          .get(targetId)
          ?.push({ neighbor: sourceId, linkId: validLinkId });
      }
    });

    interface QueueItem {
      id: string;
      depth: number;
    }
    const queue: QueueItem[] = [];
    const depthMap = new Map<string, number>();
    const linkDepthMap = new Map<string, number>();
    const remainingNodes = new Set(nodeIds);

    let currentDeepest = 0;

    while (remainingNodes.size > 0) {
      if (queue.length === 0) {
        const nextStart = remainingNodes.values().next().value;
        if (!nextStart) break;
        queue.push({ id: nextStart, depth: 0 });
        depthMap.set(nextStart, 0);
      }

      while (queue.length > 0) {
        const { id: currentId, depth: currentDepth } = queue.shift()!;
        remainingNodes.delete(currentId);

        const neighbors = adjacency.get(currentId) || [];
        for (const { neighbor, linkId } of neighbors) {
          const neighborDepth = currentDepth + 1;

          if (
            !depthMap.has(neighbor) ||
            depthMap.get(neighbor)! > neighborDepth
          ) {
            depthMap.set(neighbor, neighborDepth);
            linkDepthMap.set(linkId, neighborDepth);
            queue.push({ id: neighbor, depth: neighborDepth });
            if (neighborDepth > currentDeepest) {
              currentDeepest = neighborDepth;
            }
          } else if (!linkDepthMap.has(linkId)) {
            linkDepthMap.set(linkId, currentDepth);
          }
        }
      }
    }

    const WAVE_DELAY = 150;
    const DURATION = 600;
    const linkFadeDuration = 800;
    const globalStartTime = performance.now();

    const maxDelay = currentDeepest * WAVE_DELAY;
    const totalDuration = maxDelay + DURATION + 500;

    const animateFrame = () => {
      if (currentAnimationId !== animationId) return;

      const now = performance.now();
      const elapsedSinceStart = now - globalStartTime;
      let isAnyAnimating = false;

      nodeIds.forEach((nodeId) => {
        const depth = depthMap.get(nodeId) ?? 0;
        const delay = depth * WAVE_DELAY;
        const localElapsed = elapsedSinceStart - delay;

        if (localElapsed >= 0 && localElapsed < DURATION) {
          isAnyAnimating = true;
          const progress = localElapsed / DURATION;
          const eased = easeOutCubic(progress);

          const nodeObj = nodeMap.get(nodeId);
          if (nodeObj && nodeObj.__threeObj) {
            const obj = nodeObj.__threeObj;

            const currentOpacity = 0.1 + 0.9 * eased;

            let currentScale = eased;
            currentScale =
              progress > 0.8
                ? 1.05 - (progress - 0.8) * 0.25
                : Math.min(progress * 1.3125, 1.05);

            const origScale = obj.userData.originalScale || {
              x: 1,
              y: 1,
              z: 1,
            };
            obj.scale.set(
              origScale.x * currentScale,
              origScale.y * currentScale,
              origScale.z * currentScale,
            );

            if (obj.material) {
              obj.material.opacity = currentOpacity;
              obj.material.transparent = true;
            } else if (obj.children) {
              obj.traverse((child: any) => {
                if (child.material) {
                  child.material.opacity = currentOpacity;
                  child.material.transparent = true;
                }
              });
            }
          }
        } else if (localElapsed >= DURATION) {
          const nodeObj = nodeMap.get(nodeId);
          if (nodeObj && nodeObj.__threeObj) {
            const obj = nodeObj.__threeObj;
            const origScale = obj.userData.originalScale || {
              x: 1,
              y: 1,
              z: 1,
            };
            obj.scale.set(origScale.x, origScale.y, origScale.z);

            if (obj.material) {
              obj.material.opacity = 1;
              obj.material.transparent = false;
              obj.material.needsUpdate = true;
            } else if (obj.children) {
              obj.traverse((child: any) => {
                if (child.material) {
                  child.material.opacity = 1;
                  child.material.transparent = false;
                  child.material.needsUpdate = true;
                }
              });
            }
          }
        }
      });

      linkIds.forEach((linkId) => {
        const depth = linkDepthMap.get(linkId) ?? 0;
        const delay = depth * WAVE_DELAY + 100;
        const localElapsed = elapsedSinceStart - delay;

        if (localElapsed >= 0 && localElapsed < linkFadeDuration) {
          isAnyAnimating = true;
          const progress = localElapsed / linkFadeDuration;
          const eased = easeOutCubic(progress);

          let linkGroup = linkObjMap.get(linkId);
          if (!linkGroup) {
            const edge = links.find((e: any) => {
              const s = typeof e.source === 'object' ? e.source.id : e.source;
              const t = typeof e.target === 'object' ? e.target.id : e.target;
              return `${s}-${t}` === linkId || `${t}-${s}` === linkId;
            });
            const edgeObj = edge as any;
            if (edgeObj?.__threeObj) {
              linkGroup = edgeObj.__threeObj;
              linkObjMap.set(linkId, linkGroup);
            }
          }

          if (linkGroup) {
            const pipeMesh = linkGroup.children?.find(
              (c: any) => c.userData?.isPipe,
            );
            if (pipeMesh && pipeMesh.material && pipeMesh.material.uniforms) {
              pipeMesh.material.uniforms.progress.value = eased * 0.7;
            }
          }
        } else if (localElapsed >= linkFadeDuration) {
          const linkGroup = linkObjMap.get(linkId);
          if (linkGroup) {
            const pipeMesh = linkGroup.children?.find(
              (c: any) => c.userData?.isPipe,
            );
            if (pipeMesh && pipeMesh.material && pipeMesh.material.uniforms) {
              pipeMesh.material.uniforms.progress.value = 0.7;
            }
          }
        }
      });

      if (isAnyAnimating || elapsedSinceStart < totalDuration) {
        requestAnimationFrame(animateFrame);
      }
    };

    requestAnimationFrame(animateFrame);
  });
}

// 获取当前图谱节点列表（供父组件匹配用）
function getNodes(): GraphNode[] {
  return graphData.value.nodes;
}

// 获取当前图谱连线列表（供父组件匹配用）
function getEdges(): GraphEdge[] {
  return graphData.value.edges;
}

defineExpose({
  fetchGraphData,
  handleReset,
  handleRefresh,
  handleDownload,
  highlightElements,
  clearHighlight,
  clearGraphCache,
  getNodes,
  getEdges,
  graphData,
  filteredGraph,
});
</script>

<template>
  <div class="relative h-full w-full">
    <div
      ref="containerRef"
      class="graph-container"
      :class="{ 'cursor-wait': loading }"
    ></div>

    <!-- Loading Overlay -->
    <Transition name="fade">
      <div
        v-if="loading"
        class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-gray-900/90 backdrop-blur-md"
      >
        <!-- Tech Spinner -->
        <div class="loading-spinner mb-6">
          <div class="spinner-ring ring-1"></div>
          <div class="spinner-ring ring-2"></div>
          <div class="spinner-core"></div>
        </div>
        <div
          class="animate-pulse text-sm font-medium tracking-wider text-cyan-400"
        >
          正在构建知识图谱...
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  background-color: #0b1220;
}

.cursor-wait {
  cursor: wait;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.6s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Tech Spinner Styles */
.loading-spinner {
  position: relative;
  width: 80px;
  height: 80px;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #06b6d4; /* cyan-500 */
  border-right-color: rgba(6, 182, 212, 0.3);
  box-shadow: 0 0 10px rgba(6, 182, 212, 0.1);
}

.ring-1 {
  animation: spin 1.5s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.ring-2 {
  inset: 10px;
  border-top-color: #3b82f6; /* blue-500 */
  border-right-color: rgba(59, 130, 246, 0.3);
  animation: spin-reverse 2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-core {
  position: absolute;
  inset: 25px;
  background: radial-gradient(circle, #22d3ee 0%, #06b6d4 100%);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
  box-shadow: 0 0 15px rgba(6, 182, 212, 0.5);
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

@keyframes spin-reverse {
  0% {
    transform: rotate(360deg);
  }
  100% {
    transform: rotate(0deg);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(0.8);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.1);
    opacity: 1;
    box-shadow: 0 0 25px rgba(6, 182, 212, 0.8);
  }
}
</style>
