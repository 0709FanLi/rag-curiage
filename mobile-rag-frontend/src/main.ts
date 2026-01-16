import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import { router } from './router';
import './styles/global.css';

function set_viewport_height_css_var(): void {
  // iOS Safari 地址栏/工具栏会导致 100vh 不可靠，使用 --vh 适配真实可视高度
  const vh = window.innerHeight * 0.01;
  document.documentElement.style.setProperty('--vh', `${vh}px`);
}

set_viewport_height_css_var();
window.addEventListener('resize', set_viewport_height_css_var);
window.addEventListener('orientationchange', set_viewport_height_css_var);

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
