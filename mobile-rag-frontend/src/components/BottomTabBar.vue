<template>
  <nav class="tabbar">
    <RouterLink class="tab" :class="{ active: is_active('/chat') }" to="/chat">
      <span class="label">问诊</span>
    </RouterLink>
    <RouterLink class="tab" :class="{ active: is_active('/me') }" to="/me">
      <span class="label">我的</span>
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';

const route = useRoute();

function is_active(prefix: string): boolean {
  return route.path === prefix || route.path.startsWith(`${prefix}/`);
}
</script>

<style scoped>
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  background: var(--card);
  border-top: 1px solid var(--border);
  padding: 10px 10px calc(10px + env(safe-area-inset-bottom));
  z-index: 50;
}

.tab {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
  color: var(--muted);
  font-size: 14px;
}

.tab.active {
  color: var(--primary);
  font-weight: 600;
}
</style>


