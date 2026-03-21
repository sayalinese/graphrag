import type { MenuRecordRaw, RouteRecordStringComponent } from '@vben/types';

import { ref } from 'vue';

import { requestClient } from '#/api/request';

export interface MenuItem {
  id: number;
  pid?: number;
  type: 'button' | 'catalog' | 'embedded' | 'link' | 'menu';
  title: string;
  name?: string;
  path?: string;
  component?: string;
  icon?: string;
  redirect?: string;
  status: 0 | 1;
  children?: MenuItem[];
}

const _menus = ref<MenuItem[]>([]);

function cloneMenus() {
  return structuredClone(_menus.value);
}


function toMenuRecords(
  list: MenuItem[],
  inheritedHidden = false,
): MenuRecordRaw[] {
  return list
    .filter((item) => item.type !== 'button')
    .map((item) => {
      const hidden = inheritedHidden || item.status === 0;
      const route: MenuRecordRaw = {
        name: item.name || item.path || `${item.id}`,
        path: item.path || '',
        icon: item.icon,
        show: !hidden,
      };

      if (item.children?.length) {
        route.children = toMenuRecords(item.children, hidden);
      }
      return route;
    });
}

function filterVisibleMenuRecords(list: MenuRecordRaw[]): MenuRecordRaw[] {
  return list
    .filter((item) => item.show !== false)
    .map((item) => ({
      ...item,
      children: item.children ? filterVisibleMenuRecords(item.children) : undefined,
    }));
}

export async function getMenuRoutes() {
  return (await requestClient.get('/menu/all')) as RouteRecordStringComponent[];
}

export async function getMenuRecords() {
  if (_menus.value.length === 0) {
    await listMenusInternal();
  }
  return filterVisibleMenuRecords(toMenuRecords(cloneMenus()));
}

function normalizeTree(list: MenuItem[]): MenuItem[] {
  return list.map((item) => ({
    ...item,
    children: item.children ? normalizeTree(item.children) : undefined,
  }));
}

async function listMenusInternal() {
  const res: any = await requestClient.get('/system/menu/list');
  const menus = res?.menus || res?.data?.menus || [];
  _menus.value = normalizeTree(menus);
  return _menus.value;
}

export function useMenuApi() {
  function listMenus() {
    return listMenusInternal();
  }
  async function createMenu(data: Omit<MenuItem, 'id'>) {
    const res: any = await requestClient.post('/system/menu/create', data);
    const item = res?.menu || res?.data?.menu || null;
    await listMenusInternal();
    return item as MenuItem | null;
  }
  async function updateMenu(id: number, data: Partial<Omit<MenuItem, 'id'>>) {
    const res: any = await requestClient.request(`/system/menu/${id}`, {
      method: 'PUT',
      data,
    });
    const item = res?.menu || res?.data?.menu || null;
    await listMenusInternal();
    return item as MenuItem | null;
  }
  async function deleteMenu(id: number) {
    await requestClient.request(`/system/menu/${id}`, { method: 'DELETE' });
    await listMenusInternal();
    return true;
  }
  async function toggleMenuStatus(id: number) {
    const res: any = await requestClient.request(`/system/menu/${id}/toggle`, {
      method: 'POST',
    });
    const item = res?.menu || res?.data?.menu || null;
    await listMenusInternal();
    return item as MenuItem | null;
  }

  return {
    listMenus,
    createMenu,
    updateMenu,
    deleteMenu,
    toggleMenuStatus,
    menus: _menus,
  };
}
