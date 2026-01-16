import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

export type AuthUser = {
  identifier: string;
  user_id: number;
};

const TOKEN_KEY = 'healthy_rag_token_v2';
const USER_KEY = 'healthy_rag_user_v2';

export const use_auth_store = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '');
  const user = ref<AuthUser | null>(
    localStorage.getItem(USER_KEY) ? (JSON.parse(localStorage.getItem(USER_KEY) as string) as AuthUser) : null,
  );

  const is_logged_in = computed<boolean>(() => Boolean(token.value));

  function set_auth(new_token: string, new_user: AuthUser): void {
    token.value = new_token;
    user.value = new_user;
    localStorage.setItem(TOKEN_KEY, new_token);
    localStorage.setItem(USER_KEY, JSON.stringify(new_user));
  }

  function clear_auth(): void {
    token.value = '';
    user.value = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  return {
    token,
    user,
    is_logged_in,
    set_auth,
    clear_auth,
  };
});


