import { baseRequestClient } from '#/api/request';

export async function getDatabases() {
  return baseRequestClient.get('/kg/databases');
}

export async function getCommunities(docId?: string, database?: string) {
  return baseRequestClient.get('/kg/communities', { params: { doc_id: docId, database } });
}

export async function getVisualizeData(limit = 100, docId?: string, communityId?: number, database?: string) {
  const params: Record<string, any> = { limit };
  if (docId) params.doc_id = docId;
  if (communityId !== undefined) params.community_id = communityId;
  if (database) params.database = database;
  return baseRequestClient.get('/kg/visualize', { params });
}

export async function updateNode(nodeId: string, properties: Record<string, any>) {
  return baseRequestClient.put(`/kg/nodes/${nodeId}`, { properties });
}

export async function updateRelation(relationId: string, properties: Record<string, any>) {
  return baseRequestClient.put(`/kg/relations/${relationId}`, { properties });
}

export async function deleteNode(nodeId: string) {
  return baseRequestClient.delete(`/kg/nodes/${nodeId}`);
}

export async function deleteRelation(relationId: string) {
  return baseRequestClient.delete(`/kg/relations/${relationId}`);
}

export async function deleteDocument(docId: string) {
  return baseRequestClient.delete(`/kg/documents/${docId}`);
}

export async function exportDocument(docId: string) {
  return baseRequestClient.get(`/kg/documents/${docId}/export`);
}

export async function clearDatabase(database: string) {
  return baseRequestClient.post(`/kg/databases/${encodeURIComponent(database)}/clear`);
}

export async function exportDatabase(database: string) {
  return baseRequestClient.get(`/kg/databases/${encodeURIComponent(database)}/export`);
}

export async function cleanupVectors() {
  return baseRequestClient.post('/kg/vectors/cleanup');
}

