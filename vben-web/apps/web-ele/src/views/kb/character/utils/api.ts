// Character API 实现
import { ref } from 'vue';

import { requestClient } from '#/api/request';

function normalizeCharacter(payload: any): CharacterVO {
  return {
    id: payload?.id,
    key: payload?.key,
    name: payload?.name,
    product: payload?.product,
    hobby: payload?.hobby,
    personality: payload?.personality,
    expertise: payload?.expertise || [],
    system_prompt: payload?.system_prompt,
    avatar: payload?.avatar,
    is_active: Boolean(payload?.is_active),
    created_at: payload?.created_at,
    updated_at: payload?.updated_at,
  };
}

/** AI 角色 */
export interface CharacterVO {
  id?: number;
  key: string;
  name: string;
  product: string;
  hobby: string;
  personality: string;
  expertise: string[];
  system_prompt: string;
  avatar?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCharacterRequest {
  key: string;
  name: string;
  product: string;
  hobby: string;
  personality: string;
  expertise?: string[];
  system_prompt?: string;
  avatar?: string;
}

/** 更新角色请求 */
export interface UpdateCharacterRequest {
  name?: string;
  product?: string;
  hobby?: string;
  personality?: string;
  expertise?: string[];
  system_prompt?: string;
  avatar?: string;
  is_active?: boolean;
}

/**
 * 列出所有角色
 */
export async function listCharacters(): Promise<CharacterVO[]> {
  const res = await requestClient.get('/character/list');
  return (res.characters || []).map(normalizeCharacter);
}

/**
 * 获取角色详情
 */
export async function getCharacter(key: string): Promise<CharacterVO> {
  const res = await requestClient.get(`/character/${key}`);
  return normalizeCharacter(res.character);
}

/**
 * 获取可用的角色列表
 */
export async function getAvailableCharacters(): Promise<CharacterVO[]> {
  const res = await requestClient.get('/character/available');
  return (res.characters || []).map(normalizeCharacter);
}

/**
 * 创建角色
 */
export async function createCharacter(
  data: CreateCharacterRequest
): Promise<CharacterVO> {
  const res = await requestClient.post('/character/create', data);
  return normalizeCharacter(res.character);
}

/**
 * 更新角色
 */
export async function updateCharacter(
  id: number,
  data: UpdateCharacterRequest
): Promise<CharacterVO> {
  const res = await requestClient.put(`/character/${id}`, data);
  return normalizeCharacter(res.character);
}

/**
 * 删除角色
 */
export async function deleteCharacter(id: number): Promise<{ success: boolean }> {
  return requestClient.delete(`/character/${id}`);
}

/**
 * 切换角色启用/禁用状态
 */
export async function toggleCharacterStatus(id: number): Promise<{ success: boolean; is_active: boolean }> {
  return requestClient.post(`/character/${id}/toggle-status`);
}

export function useCharacterApi() {
  const loading = ref(false);
  const characters = ref<CharacterVO[]>([]);

  const listCharactersApi = async () => {
    loading.value = true;
    try {
      characters.value = await listCharacters();
    } finally {
      loading.value = false;
    }
  };

  return {
    loading,
    characters,
    listCharacters: listCharactersApi,
    createCharacter,
    updateCharacter,
    deleteCharacter,
    toggleCharacterStatus,
    getCharacter,
    getAvailableCharacters,
  };
}
