<template>
  <div v-if="toast.visible" class="toast">{{ toast.message }}</div>
</template>

<script setup lang="ts">
import { use_toast_store } from '../stores/toast_store';

const toast = use_toast_store();
</script>

<style scoped>
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(70px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  max-width: 86vw;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.78);
  color: #fff;
  font-size: 14px;
  line-height: 1.4;
  z-index: 9999;
}
</style>


