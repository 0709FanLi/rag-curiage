import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios';
import { use_auth_store } from '../stores/auth_store';

export function get_api_base_url(): string {
  const env_base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (env_base) {
    return env_base;
  }
  return import.meta.env.PROD ? '/api/v1' : 'http://localhost:8010/api/v1';
}

const api_client: AxiosInstance = axios.create({
  baseURL: get_api_base_url().replace(/\/+$/, ''),
  // 问卷/报告生成涉及大模型调用，生产环境偶发较慢，需要更长超时。
  // 具体接口仍可在调用处通过 config.timeout 覆盖。
  timeout: 600_000,
});

api_client.interceptors.request.use((config) => {
  const auth_store = use_auth_store();
  if (auth_store.token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${auth_store.token}`;
  }
  return config;
});

api_client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    const request_url = String(error?.config?.url || '');

    // 登录接口 401 是“用户名或密码错误”，不要误判为 token 过期
    if (status === 401 && !request_url.includes('/auth/login')) {
      const auth_store = use_auth_store();
      auth_store.clear_auth();
      // 避免循环跳转：由路由守卫接管
      if (typeof window !== 'undefined') {
        const base_url = String(import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
        window.location.href = `${base_url}login`;
      }
    }

    // 统一在页面层处理；这里只确保把 axios error 往上抛
    return Promise.reject(error);
  },
);

export async function http_request<T>(config: AxiosRequestConfig): Promise<T> {
  const resp = await api_client.request<T>(config);
  return resp.data;
}


