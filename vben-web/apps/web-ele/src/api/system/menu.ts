// 简化的本地 mock 菜单 API
import { ref } from 'vue';

export interface MenuItem {
  id: number;
  pid?: number;
  type: 'button' | 'catalog' | 'embedded' | 'link' | 'menu';
  title: string; // 直接用显示标题或 i18n 键
  path?: string;
  icon?: string;
  status: 0 | 1;
  children?: MenuItem[];
}

const _menus = ref<MenuItem[]>([
  {
    id: 1,
    type: 'catalog',
    title: 'system.menu.manager',
    status: 1,
    children: [
      {
        id: 11,
        pid: 1,
        type: 'menu',
        title: 'system.role.list',
        path: '/system/role',
        status: 1,
      },
      {
        id: 12,
        pid: 1,
        type: 'menu',
        title: 'system.menu.name',
        path: '/system/menu',
        status: 1,
      },
    ],
  },
]);

let idSeed = 1000;

export function useMenuApi() {
  function listMenus() {
    return Promise.resolve(structuredClone(_menus.value));
  }
  function createMenu(data: Omit<MenuItem, 'id'>) {
    const item: MenuItem = { ...data, id: ++idSeed };
    if (item.pid) {
      const parent = findNode(item.pid, _menus.value);
      if (parent) {
        parent.children = parent.children || [];
        parent.children.push(item);
      }
    } else {
      _menus.value.push(item);
    }
    return Promise.resolve(item);
  }
  function updateMenu(id: number, data: Partial<Omit<MenuItem, 'id'>>) {
    const node = findNode(id, _menus.value);
    if (node) {
      Object.assign(node, data);
    }
    return Promise.resolve(node);
  }
  function deleteMenu(id: number) {
    removeNode(id, _menus.value);
    return Promise.resolve(true);
  }
  function toggleMenuStatus(id: number) {
    const node = findNode(id, _menus.value);
    if (node) node.status = node.status === 1 ? 0 : 1;
    return Promise.resolve(node);
  }

  function findNode(id: number, list: MenuItem[]): MenuItem | null {
    for (const item of list) {
      if (item.id === id) return item;
      if (item.children) {
        const found = findNode(id, item.children);
        if (found) return found;
      }
    }
    return null;
  }
  function removeNode(id: number, list: MenuItem[]): boolean {
    const idx = list.findIndex((i) => i.id === id);
    if (idx !== -1) {
      list.splice(idx, 1);
      return true;
    }
    for (const item of list) {
      if (item.children && removeNode(id, item.children)) return true;
    }
    return false;
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
