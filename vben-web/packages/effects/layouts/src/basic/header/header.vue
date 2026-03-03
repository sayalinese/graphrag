<script lang="ts" setup>
import { computed, useSlots } from 'vue';

import { useRefresh } from '@vben/hooks';
import { RotateCw } from '@vben/icons';
import { preferences, usePreferences } from '@vben/preferences';
import { useAccessStore } from '@vben/stores';

import { VbenIconButton } from '@vben-core/shadcn-ui';

import { GlobalSearch, LanguageToggle, ThemeToggle } from '../../widgets';

interface Props {
  /**
   * Logo 主题
   */
  theme?: string;
}

defineOptions({
  name: 'LayoutHeader',
});

withDefaults(defineProps<Props>(), {
  theme: 'light',
});

// 隐藏后不再需要偏好登出事件
// const emit = defineEmits<{ clearPreferencesAndLogout: [] }>();

const REFERENCE_VALUE = 50;

const accessStore = useAccessStore();
const { globalSearchShortcutKey } = usePreferences();
const slots = useSlots();
const { refresh } = useRefresh();

const rightSlots = computed(() => {
  const list = [{ index: REFERENCE_VALUE + 100, name: 'user-dropdown' }];
  if (preferences.widget.globalSearch) {
    list.push({
      index: REFERENCE_VALUE,
      name: 'global-search',
    });
  }

  // preferences 已移除
  if (preferences.widget.themeToggle) {
    list.push({
      index: REFERENCE_VALUE + 20,
      name: 'theme-toggle',
    });
  }
  if (preferences.widget.languageToggle) {
    list.push({
      index: REFERENCE_VALUE + 30,
      name: 'language-toggle',
    });
  }
  // timezone/fullscreen/notification 已移除

  Object.keys(slots).forEach((key) => {
    const name = key.split('-');
    if (key.startsWith('header-right')) {
      list.push({ index: Number(name[2]), name: key });
    }
  });
  return list.sort((a, b) => a.index - b.index);
});

const leftSlots = computed(() => {
  const list: Array<{ index: number; name: string }> = [];

  if (preferences.widget.refresh) {
    list.push({
      index: 0,
      name: 'refresh',
    });
  }

  Object.keys(slots).forEach((key) => {
    const name = key.split('-');
    if (key.startsWith('header-left')) {
      list.push({ index: Number(name[2]), name: key });
    }
  });
  return list.sort((a, b) => a.index - b.index);
});

// 隐藏 Preferences 按钮后清理对应回调
</script>

<template>
  <template
    v-for="slot in leftSlots.filter((item) => item.index < REFERENCE_VALUE)"
    :key="slot.name"
  >
    <slot :name="slot.name">
      <template v-if="slot.name === 'refresh'">
        <VbenIconButton class="my-0 mr-1 rounded-md" @click="refresh">
          <RotateCw class="size-4" />
        </VbenIconButton>
      </template>
    </slot>
  </template>
  <div class="flex-center hidden lg:block">
    <slot name="breadcrumb"></slot>
  </div>
  <template
    v-for="slot in leftSlots.filter((item) => item.index > REFERENCE_VALUE)"
    :key="slot.name"
  >
    <slot :name="slot.name"></slot>
  </template>
  <div
    :class="`menu-align-${preferences.header.menuAlign}`"
    class="flex h-full min-w-0 flex-1 items-center"
  >
    <slot name="menu"></slot>
  </div>
  <div class="flex h-full min-w-0 flex-shrink-0 items-center">
    <template v-for="slot in rightSlots" :key="slot.name">
      <slot :name="slot.name">
        <template v-if="slot.name === 'global-search'">
          <GlobalSearch
            :enable-shortcut-key="globalSearchShortcutKey"
            :menus="accessStore.accessMenus"
            class="mr-1 sm:mr-4"
          />
        </template>

        <!-- preferences 已移除 -->
        <template v-else-if="slot.name === 'theme-toggle'">
          <ThemeToggle class="mr-1 mt-[2px]" />
        </template>
        <template v-else-if="slot.name === 'language-toggle'">
          <LanguageToggle class="mr-1" />
        </template>
        <!-- fullscreen 已移除 -->
        <!-- timezone/notification 已移除 -->
      </slot>
    </template>
  </div>
</template>
<style lang="scss" scoped>
.menu-align-start {
  --menu-align: start;
}

.menu-align-center {
  --menu-align: center;
}

.menu-align-end {
  --menu-align: end;
}
</style>
