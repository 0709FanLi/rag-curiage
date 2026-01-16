import { defineStore } from 'pinia';
import { ref } from 'vue';

export const use_toast_store = defineStore('toast', () => {
  const visible = ref<boolean>(false);
  const message = ref<string>('');
  let timer: number | null = null;

  function show(text: string, duration_ms: number = 1500): void {
    message.value = text;
    visible.value = true;
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    timer = window.setTimeout(() => {
      visible.value = false;
      timer = null;
    }, duration_ms);
  }

  return {
    visible,
    message,
    show,
  };
});


