import { http_request } from './http';

export type UploadFileResponse = {
  success: boolean;
  file_url: string;
  file_name: string;
  file_size: number;
  content_type: string;
  object_key?: string;
};

export async function upload_file(file: File): Promise<UploadFileResponse> {
  const form = new FormData();
  form.append('file', file);
  return await http_request<UploadFileResponse>({
    url: '/upload/file',
    method: 'POST',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  });
}


