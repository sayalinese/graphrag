// 简化的本地 mock 角色 API
import { ref } from 'vue';

export interface RoleItem {
  id: number;
  name: string;
  status: 0 | 1;
  remark?: string;
  permissions: string[];
  createTime: string;
}

const _roles = ref<RoleItem[]>([
  {
    id: 1,
    name: '超级管理员',
    status: 1,
    remark: '系统最高权限',
    permissions: ['super'],
    createTime: '2024-11-01 10:00:00',
  },
  {
    id: 2,
    name: '普通管理员',
    status: 1,
    remark: '基础管理权限',
    permissions: ['admin'],
    createTime: '2024-11-02 09:30:00',
  },
]);

export function useRoleApi() {
  function listRoles() {
    return Promise.resolve([..._roles.value]);
  }
  function createRole(data: Omit<RoleItem, 'createTime' | 'id'>) {
    const id = Date.now();
    const item: RoleItem = {
      ...data,
      id,
      createTime: new Date().toISOString().slice(0, 19).replace('T', ' '),
    };
    _roles.value.push(item);
    return Promise.resolve(item);
  }
  function updateRole(
    id: number,
    data: Partial<Omit<RoleItem, 'createTime' | 'id'>>,
  ) {
    const item = _roles.value.find((r) => r.id === id);
    if (item) {
      if (data.name !== undefined) item.name = data.name;
      if (data.status !== undefined) item.status = data.status;
      if (data.remark !== undefined) item.remark = data.remark;
      if (data.permissions !== undefined) item.permissions = data.permissions;
    }
    return Promise.resolve(item);
  }
  function deleteRole(id: number) {
    _roles.value = _roles.value.filter((r) => r.id !== id);
    return Promise.resolve(true);
  }
  function toggleStatus(id: number) {
    const item = _roles.value.find((r) => r.id === id);
    if (item) item.status = item.status === 1 ? 0 : 1;
    return Promise.resolve(item);
  }
  return {
    listRoles,
    createRole,
    updateRole,
    deleteRole,
    toggleStatus,
    roles: _roles,
  };
}
