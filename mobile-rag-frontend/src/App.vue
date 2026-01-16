<template>
  <div class="app-shell">
    <router-view class="app-view" :class="{ 'with-tabbar': !hide_tab_bar }" />
    <BottomTabBar v-if="!hide_tab_bar" />
    <ToastHost />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import BottomTabBar from './components/BottomTabBar.vue';
import ToastHost from './components/ToastHost.vue';

const route = useRoute();
const hide_tab_bar = computed<boolean>(() => Boolean(route.meta?.hide_tab_bar));
</script>

<style scoped>
.app-shell {
  height: calc(var(--vh, 1vh) * 100);
  min-height: -webkit-fill-available;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-view {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.app-view.with-tabbar {
  /* 预留底部 tabbar 的高度，避免内容被遮挡/出现额外滚动 */
  padding-bottom: calc(56px + env(safe-area-inset-bottom));
}
</style>
