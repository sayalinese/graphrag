import { ref } from 'vue';

import { requestClient } from '#/api/request';

export interface UserItem {
  id: number;
  username: string;
  avatar?: string;
  email?: string;
  permissions: string[];
  createTime: string;
  lastVisitTime?: string;
  status: 0 | 1; // 1 启用 0 禁用
}

const _users = ref<UserItem[]>([]);

function transform(raw: any): UserItem {
  return {
    id: raw.id,
    username: raw.username,
    avatar: raw.avatar,
    email: raw.email,
    permissions: raw.permissions || [],
    createTime: raw.createTime || '',
    lastVisitTime: raw.lastVisitTime || '',
    status: raw.status ?? 1,
  };
}

export function useUserApi() {
  async function listUsers(params?: {
    page?: number;
    page_size?: number;
    search?: string;
  }) {
    // 后端用户管理接口已迁移到 /api/auth/users
    const res: any = await requestClient.get('/auth/users', { params });
    const items =
      res?.data?.items ||
      res?.items ||
      res?.data?.data?.items ||
      res?.items ||
      []; // 兼容包装
    _users.value = items.map((item: any) => transform(item));
    return _users.value;
  }

  async function createUser(data: Partial<UserItem> & { password?: string }) {
    const payload: any = {
      username: data.username,
      email: data.email,
      avatar: data.avatar,
      permissions: data.permissions,
      password: data.password,
      status: data.status,
    };
    const res: any = await requestClient.post('/auth/users', payload);
    const user = res.data?.user || res.data?.data?.user;
    if (user) {
      const t = transform(user);
      _users.value.unshift(t);
      return t;
    }
    return null;
  }

  async function updateUser(
    id: number,
    data: Partial<UserItem> & { password?: string },
  ) {
    const payload: any = {
      username: data.username,
      email: data.email,
      avatar: data.avatar,
      permissions: data.permissions,
      status: data.status,
      password: (data as any).password,
    };
    const res: any = await requestClient.request(`/auth/users/${id}`, {
      method: 'PATCH',
      data: payload,
    });
    const user = res.data?.user || res.data?.data?.user;
    if (user) {
      const t = transform(user);
      const idx = _users.value.findIndex((u) => u.id === id);
      if (idx !== -1) _users.value[idx] = t;
      return t;
    }
    return null;
  }

  async function deleteUser(id: number) {
    await requestClient.request(`/auth/users/${id}`, { method: 'DELETE' });
    _users.value = _users.value.filter((u) => u.id !== id);
    return true;
  }

  async function toggleStatus(id: number) {
    const res: any = await requestClient.request(`/auth/users/${id}/toggle`, {
      method: 'POST',
    });
    const status = res.data?.status ?? res.data?.data?.status;
    const user = _users.value.find((u) => u.id === id);
    if (user && status !== undefined) user.status = status;
    return user;
  }

  function markVisit(id: number) {
    const user = _users.value.find((u) => u.id === id);
    if (user)
      user.lastVisitTime = new Date()
        .toISOString()
        .slice(0, 19)
        .replace('T', ' ');
    return Promise.resolve(user);
  }

  return {
    users: _users,
    listUsers,
    createUser,
    updateUser,
    deleteUser,
    toggleStatus,
    markVisit,
  };
}
