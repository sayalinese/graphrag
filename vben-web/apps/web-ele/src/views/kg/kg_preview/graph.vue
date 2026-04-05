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

const emit = defineEmits<{
  'stats-changed': [payload: { nodeCount: number; edgeCount: number }];
}>();

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
let focusZoomTimer: null | ReturnType<typeof setTimeout> = null;

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

    // 检查是否过�?
    if (now - entry.timestamp > GRAPH_CACHE_EXPIRY) {
      sessionStorage.removeItem(GRAPH_CACHE_KEY);
      return null;
    }

    // 检�?database �?limit 是否匹配
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

// 高亮状�?
const highlightedNodeIds = shallowRef<Set<string>>(new Set());
const highlightedLinkIds = shallowRef<Set<string>>(new Set());
const hoveredNodeIds = shallowRef<Set<string>>(new Set());
const hoveredLinkIds = shallowRef<Set<string>>(new Set());
const hoveredCenterNodeId = ref('');
const focusedNodeIds = shallowRef<Set<string>>(new Set());
const focusedLinkIds = shallowRef<Set<string>>(new Set());
const focusedSeedNodeIds = shallowRef<Set<string>>(new Set());
const isHoverHighlightActive = computed(
  () => hoveredNodeIds.value.size > 0 || hoveredLinkIds.value.size > 0,
);
const isHighlightActive = computed(
  () =>
    highlightedNodeIds.value.size > 0 ||
    highlightedLinkIds.value.size > 0 ||
    hoveredNodeIds.value.size > 0 ||
    hoveredLinkIds.value.size > 0,
);

function getActiveHighlightedNodeIds(): Set<string> {
  if (highlightedNodeIds.value.size > 0 || highlightedLinkIds.value.size > 0) {
    return highlightedNodeIds.value;
  }
  return hoveredNodeIds.value;
}

function getActiveHighlightedLinkIds(): Set<string> {
  if (highlightedNodeIds.value.size > 0 || highlightedLinkIds.value.size > 0) {
    return highlightedLinkIds.value;
  }
  return hoveredLinkIds.value;
}

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
  id?: string;
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

interface IncomingGraphPayload {
  nodes?: unknown[];
  edges?: unknown[];
  links?: unknown[];
}

const focusedGraphData = shallowRef<null | VisualizerData>(null);

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
    .map((item: any, index) => {
      const source = String(item?.source ?? item?.from ?? item?.start ?? '');
      const target = String(item?.target ?? item?.to ?? item?.end ?? '');
      const label = String(item?.label ?? item?.type ?? 'RELATED_TO');
      const value = Number(item?.value ?? item?.weight ?? 1) || 1;
      const id = String(item?.id ?? `${source}-${target}#${index}`);
      return { id, source, target, label, value } as GraphEdge;
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
  // 优先�?properties.type 获取（这�?Neo4j 实体的真实类型）
  const props = rawNode.properties || rawNode.props || rawNode.data;
  if (props && typeof props === 'object') {
    const typeValue = props.type || props.category || props.kind;
    if (typeof typeValue === 'string' && typeValue.trim() !== '') {
      return typeValue.toUpperCase();
    }
  }

  // 其次尝试直接属�?
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

  // 最后尝�?labels
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
  rawEdges.forEach((rawEdge, index) => {
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

    // 提取属�?
    const properties =
      edgeObj.properties || edgeObj.props || edgeObj.data || {};

    const edgeIdCandidate = pickFromContainers(edgeObj, [
      'id',
      'edgeId',
      'relationshipId',
      'rel_id',
    ]);
    const edgeId =
      typeof edgeIdCandidate === 'string' && edgeIdCandidate.trim() !== ''
        ? edgeIdCandidate
        : typeof edgeIdCandidate === 'number'
          ? String(edgeIdCandidate)
          : `${source}-${target}#${index}`;

    // 提取 description（优先从 properties 中获取，也可能在顶层�?
    const description =
      edgeObj.description || properties.description || properties.desc || '';

    edges.push({
      id: edgeId,
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
const nodeCount = ref(0);
const edgeCount = ref(0);
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
    const sourceGraph = focusedGraphData.value ?? graphData.value;
    const keyword = props.searchKeyword.trim().toLowerCase();
    let nodes = sourceGraph.nodes.filter((node: GraphNode) => {
      const matchesKeyword =
        keyword === '' || node.label.toLowerCase().includes(keyword);
      const matchesCategory =
        props.selectedCategory === '' ||
        node.category === props.selectedCategory;
      return matchesKeyword && matchesCategory;
    });

    if (focusedNodeIds.value.size > 0) {
      nodes = nodes.filter((node: GraphNode) => focusedNodeIds.value.has(node.id));
    }

    const visibleIds = new Set(nodes.map((node: GraphNode) => node.id));
    let edges = props.showEdges
      ? sourceGraph.edges.filter(
          (edge: GraphEdge) =>
            visibleIds.has(edge.source) && visibleIds.has(edge.target),
        )
      : [];

    if (focusedLinkIds.value.size > 0) {
      edges = edges.filter((edge: GraphEdge) => {
        const direct = `${edge.source}-${edge.target}`;
        const reverse = `${edge.target}-${edge.source}`;
        const edgeId = String(edge.id ?? '');
        return (
          (edgeId !== '' && focusedLinkIds.value.has(edgeId)) ||
          focusedLinkIds.value.has(direct) ||
          focusedLinkIds.value.has(reverse)
        );
      });
    }

    return { nodes, edges };
  },
);

const isGraphEmpty = computed(
  () => !loading.value && !hasGraphContent(filteredGraph.value),
);

function getCategoryColor(category: string): string {
  if (!category) return categoryColors.DEFAULT || '#95a5a6';
  const upperCategory = category.toUpperCase();
  // 先查预定义颜�?
  if (categoryColors[upperCategory]) {
    return categoryColors[upperCategory];
  }
  // 原始大小写也查一�?
  if (categoryColors[category]) {
    return categoryColors[category];
  }
  // 未知类别生成稳定颜色
  return hashStringToColor(upperCategory);
}

function getNodeColor(node: GraphNode): string {
  const baseColor = getCategoryColor(node.category);
  return baseColor; // 始终保持原色，仅通过透明度区�?
}

function getNodeOpacity(_node: GraphNode): number {
  // 不在这里做全局降暗；高亮态的明暗完全交给 applyNodeInteractiveState
  // 否则被点击的中心节点和相邻节点也会先被整体压暗一层�?
  return 1;
}

function applyMaterialOpacity(material: any, opacityMultiplier: number, emphasisMultiplier = 1) {
  if (!material || typeof material !== 'object') return material;

  const nextMaterial = material.clone ? material.clone() : material;
  if ('opacity' in nextMaterial && typeof nextMaterial.opacity === 'number') {
    const baseOpacity = typeof material.opacity === 'number' ? material.opacity : 1;
    const newOpacity = Math.max(0.05, Math.min(1, baseOpacity * opacityMultiplier));
    nextMaterial.opacity = newOpacity;
    // 只在 opacity < 1 时才强制 transparent，保留不透明材质（如核心球）原本的渲染通道
    if ('transparent' in nextMaterial && newOpacity < 1) {
      nextMaterial.transparent = true;
    }
  }
  if ('emissiveIntensity' in nextMaterial && typeof nextMaterial.emissiveIntensity === 'number') {
    const baseEmissiveIntensity =
      typeof material.emissiveIntensity === 'number' ? material.emissiveIntensity : 0;
    nextMaterial.emissiveIntensity = baseEmissiveIntensity * emphasisMultiplier;
  }
  return nextMaterial;
}

function applyNodeInteractiveState(object3d: any, node: GraphNode) {
  if (!object3d || !isHighlightActive.value) return object3d;

  const activeNodeIds = getActiveHighlightedNodeIds();
  if (activeNodeIds.size === 0) return object3d;

  const nodeId = String(node.id ?? '');
  const isNeighborHighlighted = activeNodeIds.has(nodeId);

  // 非高亮节点保持原样，不做任何暗化或缩�?
  if (!isNeighborHighlighted) return object3d;

  const isHoverCenter = isHoverHighlightActive.value && hoveredCenterNodeId.value === nodeId;
  const scaleMultiplier = isHoverCenter ? 1.12 : 1.04;
  const emphasisMultiplier = isHoverCenter ? 1.45 : 1.08;

  object3d.scale.multiplyScalar(scaleMultiplier);
  object3d.traverse?.((child: any) => {
    if (!child?.material) return;
    if (Array.isArray(child.material)) {
      child.material = child.material.map((material: any) =>
        applyMaterialOpacity(material, 1, emphasisMultiplier),
      );
      return;
    }
    child.material = applyMaterialOpacity(child.material, 1, emphasisMultiplier);
  });

  return object3d;
}

function getLinkColor(link: GraphEdge): string {
  if (!isHighlightActive.value) return 'rgba(102,128,255,0.6)';

  const activeNodeIds = getActiveHighlightedNodeIds();
  const activeLinkIds = getActiveHighlightedLinkIds();

  // 检查两端节点是否都被高亮，如果不是则完全隐藏这条边
  const sourceId =
    typeof link.source === 'object' ? (link.source as any).id : link.source;
  const targetId =
    typeof link.target === 'object' ? (link.target as any).id : link.target;

  const sourceHighlighted = activeNodeIds.has(sourceId);
  const targetHighlighted = activeNodeIds.has(targetId);

  if (!sourceHighlighted || !targetHighlighted) {
    // 高亮时，非路径区域连线不再完全隐藏，保留弱可见背景，避免“线消失”错�?
    return 'rgba(102,128,255,0.35)';
  }

  const linkKey = `${sourceId}-${targetId}`;
  const linkKeyReverse = `${targetId}-${sourceId}`;
  const isHighlighted =
    activeLinkIds.has(linkKey) ||
    activeLinkIds.has(linkKeyReverse);

  // 路径上的边保持弱可见，叠�?pipe 动画后更接近 explain 的逐步显现
  if (isHoverHighlightActive.value) {
    return isHighlighted ? 'rgba(94,234,212,0.92)' : 'rgba(94,234,212,0.28)';
  }
  return isHighlighted ? 'rgba(102,128,255,0.2)' : 'rgba(102,128,255,0.1)';
}

function getLinkWidth(link: GraphEdge): number {
  const baseWidth = Math.max((link.value ?? 1) * 0.45, 1.2);
  if (!isHighlightActive.value) return baseWidth;
  const activeNodeIds = getActiveHighlightedNodeIds();
  const activeLinkIds = getActiveHighlightedLinkIds();
  // 生成连线的匹�?ID
  const sourceId =
    typeof link.source === 'object' ? (link.source as any).id : link.source;
  const targetId =
    typeof link.target === 'object' ? (link.target as any).id : link.target;

  // 检查两端节点是否都被高亮，如果不是则宽度为0
  const sourceHighlighted = activeNodeIds.has(sourceId);
  const targetHighlighted = activeNodeIds.has(targetId);
  if (!sourceHighlighted || !targetHighlighted) {
    return baseWidth * 0.25;
  }

  const linkKey = `${sourceId}-${targetId}`;
  const linkKeyReverse = `${targetId}-${sourceId}`;
  const isHighlighted =
    activeLinkIds.has(linkKey) ||
    activeLinkIds.has(linkKeyReverse);
  if (isHoverHighlightActive.value) {
    return isHighlighted ? baseWidth * 2.8 : baseWidth * 1.1;
  }
  return isHighlighted ? baseWidth * 2.5 : baseWidth * 0.5;
}

function normalizeIncomingGraphPayload(
  payload?: IncomingGraphPayload,
): null | VisualizerData {
  if (!payload) return null;
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload.edges)
    ? payload.edges
    : Array.isArray(payload.links)
      ? payload.links
      : [];
  if (!nodes.length && !edges.length) return null;

  let normalized = normalizeBackendGraph(nodes, edges);
  if (!hasGraphContent(normalized)) {
    normalized = fallbackNormalizeGraph(nodes, edges);
  }
  return hasGraphContent(normalized) ? normalized : null;
}

function resolveNodeRenderer(styleKey: string) {
  const renderer = nodeStyleDefinitions[styleKey];
  if (renderer) return renderer;
  return nodeStyleDefinitions.style1 ?? Object.values(nodeStyleDefinitions)[0];
}

function shouldShowDenseLabel(node: GraphNode): boolean {
  if (!props.showLabels) return false;
  if (focusedNodeIds.value.size === 0) return true;

  const focusedCount = focusedNodeIds.value.size;
  if (focusedCount <= 24) return true;
  if (focusedSeedNodeIds.value.has(node.id)) return true;

  const value = Number(node.value ?? 1);
  if (focusedCount <= 60) {
    return value >= 3;
  }
  return value >= 6;
}

function scheduleFocusZoomToFit(duration = 900, padding = 80, delay = 260) {
  if (!graphInstance) return;
  if (focusZoomTimer) {
    clearTimeout(focusZoomTimer);
  }
  focusZoomTimer = setTimeout(() => {
    if (!graphInstance) return;
    const focusedSet = focusedNodeIds.value;
    if (focusedSet.size === 0) return;
    (graphInstance as any).zoomToFit?.(
      duration,
      padding,
      (node: any) => focusedSet.has(String(node?.id ?? '')),
    );
    focusZoomTimer = null;
  }, delay);
}

function createNodeObject(node: GraphNode): any {
  const THREE = ensureThree();
  if (!THREE) {
    return new SpriteText(node.label);
  }

  // 移除降级逻辑，保持高亮模式下节点样式与默认模式一�?
  // 仅通过透明度区分高亮与非高�?

  const renderer = resolveNodeRenderer(props.nodeStyle);
  const rendered = renderer?.({
    THREE,
    node,
    getCategoryColor,
    nodeSize: props.nodeSize,
    showLabels: shouldShowDenseLabel(node),
  });
  if (rendered) return applyNodeInteractiveState(rendered, node);
  const fallbackLabel = new SpriteText(node.label);
  fallbackLabel.color = getCategoryColor(node.category);
  return applyNodeInteractiveState(fallbackLabel, node);
}

function clearHoverHighlight() {
  hoveredCenterNodeId.value = '';
  hoveredNodeIds.value = new Set();
  hoveredLinkIds.value = new Set();
}

function collectHoverNeighborhood(nodeId: string) {
  const sourceGraph = focusedGraphData.value ?? filteredGraph.value;
  const nextNodeIds = new Set<string>([nodeId]);
  const nextLinkIds = new Set<string>();

  sourceGraph.edges.forEach((edge: GraphEdge) => {
    const sourceId = String(edge.source);
    const targetId = String(edge.target);
    if (sourceId !== nodeId && targetId !== nodeId) return;

    nextNodeIds.add(sourceId);
    nextNodeIds.add(targetId);
    if (edge.id) {
      nextLinkIds.add(String(edge.id));
    }
    nextLinkIds.add(`${sourceId}-${targetId}`);
    nextLinkIds.add(`${targetId}-${sourceId}`);
  });

  return { nextLinkIds, nextNodeIds };
}

function handleNodeActivate(node: null | NodeObject) {
  if (highlightedNodeIds.value.size > 0 || highlightedLinkIds.value.size > 0) {
    return;
  }

  const hoveredId = String((node as any)?.id ?? '');
  if (!hoveredId) {
    if (!isHoverHighlightActive.value) return;
    clearHoverHighlight();
    refreshNodeAppearance();
    applyLinkStyles();
    return;
  }

  if (hoveredCenterNodeId.value === hoveredId) {
    clearHoverHighlight();
    refreshNodeAppearance();
    applyLinkStyles();
    return;
  }

  const { nextLinkIds, nextNodeIds } = collectHoverNeighborhood(hoveredId);
  hoveredCenterNodeId.value = hoveredId;
  hoveredNodeIds.value = nextNodeIds;
  hoveredLinkIds.value = nextLinkIds;

  refreshNodeAppearance();
  applyLinkStyles();
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
  graphInstance.linkOpacity(isHighlightActive.value ? 0.28 : 0.45);
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
						<span>�?/span>
						<span class="truncate max-w-[80px]">${target}</span>
					</div>
				</div>
			`;
    })
    .linkOpacity(0.35)
    .linkColor((link: GraphEdge) => getLinkColor(link))
    .warmupTicks(60)
    .cooldownTicks(150)
    .onNodeClick((node: null | NodeObject) => {
      handleNodeActivate(node);
    })
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

async function fetchGraphData(forceRefresh = false) {
  loading.value = true;
  try {
    const effectiveLimit = Math.max(
      100,
      Math.min(5000, Number(props.graphLimit) || 300),
    );
    const selectedDatabase = props.selectedDatabase?.trim() || '';

    if (selectedDatabase.toLowerCase() === 'system') {
      throw new Error('system 数据库不支持图谱预览');
    }

    // 尝试从缓存获取数据（除非强制刷新）
    if (!forceRefresh) {
      const cachedData = getGraphCache(selectedDatabase, effectiveLimit);
      if (cachedData) {
        graphData.value = cachedData;
        nodeCount.value = cachedData.nodes.length;
        edgeCount.value = cachedData.edges.length;
        emit('stats-changed', { nodeCount: cachedData.nodes.length, edgeCount: cachedData.edges.length });
        updateGraphData();
        setTimeout(() => {
          loading.value = false;
        }, 200);
        return;
      }
    }

    // 构建带数据库参数的 URL
    const urlParams = new URLSearchParams({ limit: String(effectiveLimit) });
    if (selectedDatabase) {
      urlParams.append('database', selectedDatabase);
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
      graphData.value = { nodes: [], edges: [] };
      nodeCount.value = 0;
      edgeCount.value = 0;
      emit('stats-changed', { nodeCount: 0, edgeCount: 0 });
      updateGraphData();
      return;
    }
    graphData.value = normalized;
    nodeCount.value = normalized.nodes.length;
    edgeCount.value = normalized.edges.length;
    emit('stats-changed', { nodeCount: normalized.nodes.length, edgeCount: normalized.edges.length });
    setGraphCache(normalized, selectedDatabase, effectiveLimit);
    updateGraphData();
  } catch (error) {
    console.warn('获取知识图谱数据失败', error);
    const reason = error instanceof Error ? error.message : '未知错误';
    ElMessage.error(`图谱加载失败：${reason}`);
  } finally {
    // 延迟关闭 loading，让图谱有时间渲染和布局，配合淡出动画实现丝滑过渡
    setTimeout(() => {
      loading.value = false;
    }, 600);
  }
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
  fetchGraphData(true);
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
  () => fetchGraphData(),
);
watch(
  () => props.graphLimit,
  () => {
    if (graphLimitFetchTimer) {
      clearTimeout(graphLimitFetchTimer);
    }
    graphLimitFetchTimer = setTimeout(() => {
      fetchGraphData(true);
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
  await fetchGraphData();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateGraphSize);
  if (graphLimitFetchTimer) {
    clearTimeout(graphLimitFetchTimer);
    graphLimitFetchTimer = null;
  }
  if (focusZoomTimer) {
    clearTimeout(focusZoomTimer);
    focusZoomTimer = null;
  }
  disposeParticleBackground();
  if (graphInstance) {
    (graphInstance as unknown as { _destructor?: () => void })._destructor?.();
    graphInstance = null;
  }
});

function clearHighlight() {
  currentAnimationId++;
  focusedGraphData.value = null;
  clearHoverHighlight();
  focusedNodeIds.value.clear();
  focusedLinkIds.value.clear();
  focusedSeedNodeIds.value.clear();
  highlightedNodeIds.value.clear();
  highlightedLinkIds.value.clear();

  if (!graphInstance) return;

  updateGraphData();
  applyLinkStyles();

  const { links } = graphInstance.graphData();
  links.forEach((l: any) => {
    if (!l.__threeObj) return;
    l.__threeObj.traverse((c: any) => {
      if (c.userData?.isPipe || c.userData?.isLabel) {
        c.visible = false;
      }
    });
  });
}

function highlightElements(
  nodeIds: string[],
  linkIds: string[],
  options?: {
    maxDepth?: number;
    seedNodeIds?: string[];
    graph?: IncomingGraphPayload;
  },
) {
  currentAnimationId++;

  const payloadGraph = normalizeIncomingGraphPayload(options?.graph);
  focusedGraphData.value = payloadGraph;

  const effectiveNodes = payloadGraph?.nodes ?? graphData.value.nodes;
  const effectiveEdges = payloadGraph?.edges ?? graphData.value.edges;
  const effectiveNodeSet = new Set(effectiveNodes.map((n) => String(n.id)));

  const normalizedNodeSet = new Set(
    nodeIds
      .map((id) => String(id))
      .filter((id) => Boolean(id) && effectiveNodeSet.has(id)),
  );

  if (normalizedNodeSet.size === 0 && effectiveNodes.length > 0) {
    effectiveNodes.forEach((node) => normalizedNodeSet.add(String(node.id)));
  }

  const normalizedLinkSet = new Set(
    linkIds.map((id) => String(id)).filter(Boolean),
  );

  const availableLinkKeys = new Set<string>();
  effectiveEdges.forEach((edge: GraphEdge) => {
    availableLinkKeys.add(`${edge.source}-${edge.target}`);
    availableLinkKeys.add(`${edge.target}-${edge.source}`);
    if (edge.id) {
      availableLinkKeys.add(String(edge.id));
    }
  });

  const matchedLinkSet = new Set(
    Array.from(normalizedLinkSet).filter((id) => availableLinkKeys.has(id)),
  );

  if (matchedLinkSet.size === 0 && normalizedNodeSet.size > 1) {
    effectiveEdges.forEach((edge: GraphEdge) => {
      if (
        normalizedNodeSet.has(String(edge.source)) &&
        normalizedNodeSet.has(String(edge.target))
      ) {
        if (edge.id) {
          matchedLinkSet.add(String(edge.id));
        }
        matchedLinkSet.add(`${edge.source}-${edge.target}`);
      }
    });
  }

  focusedNodeIds.value = normalizedNodeSet;
  focusedLinkIds.value = matchedLinkSet;
  focusedSeedNodeIds.value = new Set(
    (options?.seedNodeIds ?? []).map((id) => String(id)).filter((id) =>
      normalizedNodeSet.has(id),
    ),
  );

  clearHoverHighlight();
  highlightedNodeIds.value.clear();
  highlightedLinkIds.value.clear();

  updateGraphData();
  applyLinkStyles();
  graphInstance?.d3ReheatSimulation?.();
  scheduleFocusZoomToFit();
}

// 获取当前图谱节点列表
function getNodes(): GraphNode[] {
  return graphData.value.nodes;
}

// 获取当前图谱连线列表
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
  nodeCount,
  edgeCount,
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

    <Transition name="fade">
      <div
        v-if="isGraphEmpty"
        class="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center bg-[radial-gradient(circle_at_center,rgba(8,145,178,0.14),rgba(11,18,32,0.94)_55%)] text-center"
      >
        <div class="mb-3 text-lg font-semibold tracking-wide text-cyan-300">
          当前数据库暂无可展示图谱
        </div>
        <div class="max-w-md px-6 text-sm leading-6 text-slate-400">
          可以切换数据库、放宽筛选条件，或先执行图谱构建后再查看预览
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
