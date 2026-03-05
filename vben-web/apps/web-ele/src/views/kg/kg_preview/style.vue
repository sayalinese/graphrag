<script lang="ts">
import SpriteText from 'three-spritetext';

export interface StyledNode {
  id: string;
  label: string;
  value?: number;
  category?: string;
}

export interface NodeStyleContext {
  THREE: Record<string, any>;
  node: StyledNode;
  getCategoryColor: (category: string) => string;
  nodeSize: number;
  showLabels: boolean;
}

export type NodeStyleRenderer = (context: NodeStyleContext) => any;

function createLabel(nodeLabel: string, radius: number, categoryColor: string) {
  const label = new SpriteText(nodeLabel);
  label.color = '#f4f8ff';
  label.textHeight = 10;
  label.backgroundColor = 'rgba(12, 24, 48, 0.78)';
  label.borderColor = `${categoryColor}CC`;
  label.borderWidth = 1.2;
  label.padding = [4, 8];
  label.fontWeight = '600';
  label.borderRadius = 6;
  const sprite = label as unknown as {
    material?: { depthWrite: boolean };
    position: { set: (x: number, y: number, z: number) => void };
  };
  if (sprite.material) sprite.material.depthWrite = false;
  sprite.position.set(0, radius + 15, 0);
  return label;
}

// Global caches for performance
const geometryCache: Record<string, any> = {};
const materialCache: Record<string, any> = {};

function getGeometry(THREE: any, type: string, createFn: () => any) {
  if (!geometryCache[type]) {
    geometryCache[type] = createFn();
  }
  return geometryCache[type];
}

function getMaterial(type: string, colorHex: number, createFn: () => any) {
  const key = `${type}_${colorHex}`;
  if (!materialCache[key]) {
    materialCache[key] = createFn();
  }
  return materialCache[key];
}

function createStyleOne(context: NodeStyleContext) {
  const { THREE, node, getCategoryColor, nodeSize, showLabels } = context;
  const group = new THREE.Group();
  const categoryColor = getCategoryColor(node.category ?? '');
  const baseColor = new THREE.Color(categoryColor);
  const radius = Math.max(((node.value ?? 10) * 0.12 + 6) * nodeSize, 8);

  const glowColor = baseColor.clone().lerp(new THREE.Color('#4ecdc4'), 0.25);
  const highlightColor = baseColor
    .clone()
    .lerp(new THREE.Color('#ffffff'), 0.45);

  const meshGroup = new THREE.Group();
  meshGroup.scale.set(radius, radius, radius);

  // Core Sphere
  const coreGeom = getGeometry(
    THREE,
    'style1_core',
    () => new THREE.SphereGeometry(0.6, 24, 24),
  );
  const coreMat = getMaterial(
    'style1_core',
    highlightColor.getHex(),
    () =>
      new THREE.MeshStandardMaterial({
        color: highlightColor,
        emissive: glowColor,
        emissiveIntensity: 0.7,
        metalness: 0.6,
        roughness: 0.2,
      }),
  );
  meshGroup.add(new THREE.Mesh(coreGeom, coreMat));

  // Shell Sphere
  const shellGeom = getGeometry(
    THREE,
    'style1_shell',
    () => new THREE.SphereGeometry(1, 32, 24),
  );
  const shellMat = getMaterial('style1_shell', baseColor.getHex(), () => {
    return THREE.MeshPhysicalMaterial
      ? new THREE.MeshPhysicalMaterial({
          color: baseColor,
          transparent: true,
          opacity: 0.3,
          transmission: 0.8,
          roughness: 0.1,
          metalness: 0.3,
        })
      : new THREE.MeshStandardMaterial({
          color: baseColor,
          transparent: true,
          opacity: 0.3,
          metalness: 0.3,
          roughness: 0.1,
        });
  });
  const shellMesh = new THREE.Mesh(shellGeom, shellMat);
  shellMesh.renderOrder = 1;
  meshGroup.add(shellMesh);

  // Highlight
  const hlGeom = getGeometry(
    THREE,
    'style1_hl',
    () =>
      new THREE.SphereGeometry(1.04, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2.4),
  );
  const hlMat = getMaterial(
    'style1_hl',
    16_777_215,
    () =>
      new THREE.MeshBasicMaterial({
        color: '#ffffff',
        transparent: true,
        opacity: 0.15,
        side: THREE.BackSide,
        depthWrite: false,
      }),
  );
  const hlMesh = new THREE.Mesh(hlGeom, hlMat);
  hlMesh.rotation.set(-Math.PI / 7, Math.PI / 6, 0);
  meshGroup.add(hlMesh);

  if (THREE.TorusGeometry) {
    const orbitGeom = getGeometry(
      THREE,
      'style1_orbit',
      () => new THREE.TorusGeometry(1.35, 0.05, 8, 32),
    );
    const orbitMat = getMaterial(
      'style1_orbit',
      highlightColor.getHex(),
      () =>
        new THREE.MeshBasicMaterial({
          color: highlightColor,
          transparent: true,
          opacity: 0.3,
        }),
    );
    const orbitMesh = new THREE.Mesh(orbitGeom, orbitMat);
    orbitMesh.rotation.x = Math.PI / 2.6;
    orbitMesh.rotation.z = Math.PI / 4;
    meshGroup.add(orbitMesh);
  }

  group.add(meshGroup);

  // PointLight has been removed - dramatically saves draw calls & performance
  if (showLabels) {
    group.add(createLabel(node.label, radius, categoryColor));
  }

  return group;
}

function createStyleTwo(context: NodeStyleContext) {
  const { THREE, node, getCategoryColor, nodeSize, showLabels } = context;
  const group = new THREE.Group();
  const categoryColor = getCategoryColor(node.category ?? '');
  const baseColor = new THREE.Color(categoryColor);
  const radius = Math.max(((node.value ?? 10) * 0.12 + 6) * nodeSize, 8);

  const meshGroup = new THREE.Group();
  meshGroup.scale.set(radius, radius, radius);

  const polyGeom = getGeometry(
    THREE,
    'style2_poly',
    () => new THREE.IcosahedronGeometry(0.9, 1),
  );
  const polyMat = getMaterial(
    'style2_poly',
    baseColor.getHex(),
    () =>
      new THREE.MeshStandardMaterial({
        color: baseColor,
        metalness: 0.45,
        roughness: 0.35,
        emissive: baseColor.clone().multiplyScalar(0.2),
        flatShading: true,
      }),
  );
  meshGroup.add(new THREE.Mesh(polyGeom, polyMat));

  const ringGeom = getGeometry(
    THREE,
    'style2_ring',
    () => new THREE.RingGeometry(1.05, 1.2, 32),
  );
  const ringMat = getMaterial(
    'style2_ring',
    baseColor.getHex(),
    () =>
      new THREE.MeshBasicMaterial({
        color: baseColor.clone().lerp(new THREE.Color('#00f5d4'), 0.4),
        transparent: true,
        opacity: 0.4,
        side: THREE.DoubleSide,
      }),
  );
  const ringMesh = new THREE.Mesh(ringGeom, ringMat);
  ringMesh.rotation.x = Math.PI / 2;
  meshGroup.add(ringMesh);

  group.add(meshGroup);

  if (showLabels) {
    group.add(createLabel(node.label, radius * 0.9, categoryColor));
  }

  return group;
}

export const nodeStyleDefinitions: Record<string, NodeStyleRenderer> = {
  style1: createStyleOne,
  style2: createStyleTwo,
};

export type NodeStyleKey = keyof typeof nodeStyleDefinitions;

export default {};
</script>

<template><div style="display: none"></div></template>
