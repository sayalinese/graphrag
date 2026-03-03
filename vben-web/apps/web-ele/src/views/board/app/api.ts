/**
 * 视觉RAG API接口
 * 
 * 当前使用Mock数据，将来可以替换为真实API调用
 */

import type { ImageItem, RAGResult, BoardStats } from '../mock/data';

/**
 * 搜索图像参数
 */
export interface SearchImagesParams {
  query: string;
  topK: number;
  threshold?: number;
  mode?: 'semantic' | 'visual' | 'hybrid';
}

/**
 * 搜索图像响应
 */
export interface SearchImagesResponse {
  results: RAGResult[];
  searchTime: number;
  total: number;
}

/**
 * 上传图像参数
 */
export interface UploadImageParams {
  file: File;
  title: string;
  description?: string;
  tags?: string[];
}

/**
 * API基础路径
 */
const API_BASE_URL = '/api/visual-rag';

/**
 * 搜索图像
 * @param params 搜索参数
 * @returns 搜索结果
 */
export const searchImages = async (
  params: SearchImagesParams,
): Promise<SearchImagesResponse> => {
  // TODO: 实现真实API调用
  // const response = await fetch(`${API_BASE_URL}/search`, {
  //   method: 'POST',
  //   headers: {
  //     'Content-Type': 'application/json',
  //   },
  //   body: JSON.stringify(params),
  // });
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 获取所有图像
 * @returns 图像列表
 */
export const getImages = async (): Promise<ImageItem[]> => {
  // TODO: 实现真实API调用
  // const response = await fetch(`${API_BASE_URL}/images`);
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 获取统计数据
 * @returns 统计信息
 */
export const getStats = async (): Promise<BoardStats> => {
  // TODO: 实现真实API调用
  // const response = await fetch(`${API_BASE_URL}/stats`);
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 上传图像
 * @param params 上传参数
 * @returns 上传后的图像信息
 */
export const uploadImage = async (
  params: UploadImageParams,
): Promise<ImageItem> => {
  // TODO: 实现真实API调用
  // const formData = new FormData();
  // formData.append('file', params.file);
  // formData.append('title', params.title);
  // if (params.description) {
  //   formData.append('description', params.description);
  // }
  // if (params.tags) {
  //   formData.append('tags', JSON.stringify(params.tags));
  // }
  // 
  // const response = await fetch(`${API_BASE_URL}/upload`, {
  //   method: 'POST',
  //   body: formData,
  // });
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 删除图像
 * @param imageId 图像ID
 */
export const deleteImage = async (imageId: number): Promise<void> => {
  // TODO: 实现真实API调用
  // await fetch(`${API_BASE_URL}/images/${imageId}`, {
  //   method: 'DELETE',
  // });
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 获取图像详情
 * @param imageId 图像ID
 * @returns 图像详情
 */
export const getImageDetail = async (imageId: number): Promise<ImageItem> => {
  // TODO: 实现真实API调用
  // const response = await fetch(`${API_BASE_URL}/images/${imageId}`);
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};

/**
 * 批量搜索图像
 * @param queries 多个查询
 * @returns 批量搜索结果
 */
export const batchSearchImages = async (
  queries: string[],
  topK: number = 5,
): Promise<Map<string, RAGResult[]>> => {
  // TODO: 实现真实API调用
  // const response = await fetch(`${API_BASE_URL}/batch-search`, {
  //   method: 'POST',
  //   headers: {
  //     'Content-Type': 'application/json',
  //   },
  //   body: JSON.stringify({ queries, topK }),
  // });
  // return response.json();
  
  throw new Error('API未实现，请使用Mock数据');
};


