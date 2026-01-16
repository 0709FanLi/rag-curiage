import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

import LoginPage from '../views/LoginPage.vue';
import RegisterPage from '../views/RegisterPage.vue';
import ChatPage from '../views/ChatPage.vue';
import ReportsPage from '../views/ReportsPage.vue';
import ReportDetailPage from '../views/ReportDetailPage.vue';
import MePage from '../views/MePage.vue';
import ConversationsPage from '../views/ConversationsPage.vue';
import ChatDetailPage from '../views/ChatDetailPage.vue';
import { use_auth_store } from '../stores/auth_store';

type AppRouteMeta = {
  requires_auth?: boolean;
  hide_tab_bar?: boolean;
};

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  {
    path: '/login',
    component: LoginPage,
    meta: { hide_tab_bar: true } satisfies AppRouteMeta,
  },
  {
    path: '/register',
    component: RegisterPage,
    meta: { hide_tab_bar: true } satisfies AppRouteMeta,
  },
  {
    path: '/chat',
    component: ChatPage,
    meta: { requires_auth: true } satisfies AppRouteMeta,
  },
  {
    path: '/chat/:session_id',
    component: ChatDetailPage,
    props: true,
    meta: { requires_auth: true, hide_tab_bar: true } satisfies AppRouteMeta,
  },
  {
    path: '/reports',
    component: ReportsPage,
    meta: { requires_auth: true } satisfies AppRouteMeta,
  },
  {
    path: '/report/:session_id',
    component: ReportDetailPage,
    props: true,
    meta: { requires_auth: true, hide_tab_bar: true } satisfies AppRouteMeta,
  },
  {
    path: '/conversations',
    component: ConversationsPage,
    meta: { requires_auth: true } satisfies AppRouteMeta,
  },
  {
    path: '/me',
    component: MePage,
    meta: { requires_auth: true } satisfies AppRouteMeta,
  },
];

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to) => {
  const meta = to.meta as AppRouteMeta;
  if (!meta.requires_auth) {
    return true;
  }
  const auth_store = use_auth_store();
  if (auth_store.token) {
    return true;
  }
  return { path: '/login', query: { redirect: to.fullPath } };
});


