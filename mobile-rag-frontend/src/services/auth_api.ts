import { http_request } from './http';

export type LoginResponse = {
  access_token: string;
  token_type: string;
  username: string;
  user_id: number;
};

export async function send_email_code(email: string): Promise<{ message: string }> {
  return await http_request<{ message: string }>({
    url: '/auth/email/code',
    method: 'POST',
    data: { email },
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function register_with_email(payload: {
  email: string;
  phone: string;
  password: string;
  email_code: string;
}): Promise<{ message: string; user_id: number }> {
  return await http_request<{ message: string; user_id: number }>({
    url: '/auth/register',
    method: 'POST',
    data: payload,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function login_form(identifier: string, password: string): Promise<LoginResponse> {
  // 复用后端 OAuth2PasswordRequestForm（urlencoded）
  const data = new URLSearchParams();
  data.set('username', identifier);
  data.set('password', password);
  return await http_request<LoginResponse>({
    url: '/auth/login',
    method: 'POST',
    data,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}


