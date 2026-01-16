import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, BinaryIO
from urllib.parse import quote, unquote

import oss2
from oss2.exceptions import OssError
from src.config.settings import settings

class OSSService:
    """阿里云OSS服务类."""

    def __init__(self) -> None:
        """初始化OSS服务."""
        self.access_key_id = settings.OSS_ACCESS_KEY_ID
        self.access_key_secret = settings.OSS_ACCESS_KEY_SECRET
        self.endpoint = settings.OSS_ENDPOINT
        self.bucket_name = settings.OSS_BUCKET_NAME
        self.public_read = settings.OSS_PUBLIC_READ
        self.url_expire_seconds = 3600
        self.max_file_size = 50 * 1024 * 1024  # 50MB

        # 检查配置是否完整
        self._is_configured = bool(
            self.access_key_id and
            self.access_key_secret and
            self.bucket_name and
            self.access_key_id != "your_access_key_id"
        )

        # 初始化OSS客户端
        self.auth = None
        self.bucket = None

        if self._is_configured:
            try:
                self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                self.bucket = oss2.Bucket(
                    self.auth,
                    self.endpoint,
                    self.bucket_name
                )
            except Exception as e:
                print(f"OSS初始化失败: {e}")
                self._is_configured = False
        else:
            print("OSS配置不完整，请检查 settings.py")

    def _ensure_configured(self) -> None:
        """确保OSS已配置，否则抛出异常."""
        if not self._is_configured or not self.bucket:
            raise Exception("OSS服务未配置，请检查 settings.py")

    def _generate_object_key(
        self,
        category: str,
        filename: str,
        use_date_path: bool = True
    ) -> str:
        """生成OSS对象键（文件路径）."""
        # 生成唯一ID
        unique_id = uuid.uuid4().hex[:8]

        # 处理文件名（保留扩展名）
        name, ext = os.path.splitext(filename)
        safe_filename = f"{unique_id}_{name}{ext}"

        # 构建路径
        if use_date_path:
            now = datetime.now()
            date_path = now.strftime("%Y/%m/%d")
            object_key = f"{category}/{date_path}/{safe_filename}"
        else:
            object_key = f"{category}/{safe_filename}"

        return object_key

    def _get_public_url(self, object_key: str) -> str:
        """获取公共访问URL."""
        # 移除 endpoint 中的 https://
        endpoint_domain = self.endpoint.replace('https://', '').replace('http://', '')
        return f"https://{self.bucket_name}.{endpoint_domain}/{quote(object_key)}"

    def _get_signed_url(self, object_key: str, expires: int = None) -> str:
        """获取带签名的URL."""
        if expires is None:
            expires = self.url_expire_seconds

        try:
            url = self.bucket.sign_url('GET', object_key, expires)
            return url
        except Exception as e:
            print(f"生成签名URL失败: {e}")
            return self._get_public_url(object_key)

    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        category: str = "uploads",
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """上传文件到OSS."""
        self._ensure_configured()

        # 读取文件内容
        if hasattr(file_data, 'read'):
             file_content = file_data.read()
        else:
             file_content = file_data
             
        file_size = len(file_content)

        # 检查文件大小
        if file_size > self.max_file_size:
            raise Exception(f"文件大小超过限制: {file_size / 1024 / 1024:.2f}MB")

        # 生成对象键
        object_key = self._generate_object_key(category, filename)

        # 设置请求头
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type

        # 上传文件
        result = self.bucket.put_object(
            object_key,
            file_content,
            headers=headers
        )

        # 获取访问URL
        if self.public_read:
            url = self._get_public_url(object_key)
        else:
            url = self._get_signed_url(object_key)

        return {
            "object_key": object_key,
            "url": url,
            "size": file_size,
            "content_type": content_type,
            "etag": result.etag,
            "bucket": self.bucket_name
        }

    def delete_file(self, object_key: str) -> bool:
        """删除OSS文件."""
        self._ensure_configured()

        try:
            self.bucket.delete_object(object_key)
            return True
        except OssError as e:
            raise Exception(f"OSS删除失败: {e.code} - {e.message}")

    def download_file(self, url: str) -> bytes:
        """下载文件（通过URL或object_key）."""
        # 从URL中提取object_key
        if url.startswith('http'):
            # 检查是否是我们自己的OSS bucket
            endpoint_domain = self.endpoint.replace('https://', '').replace('http://', '')
            is_our_oss = self.bucket_name in url and endpoint_domain in url

            if not is_our_oss:
                # 不是我们的OSS，直接通过HTTP下载
                import httpx
                import asyncio
                # 这里需要同步下载，或者改为异步方法。由于这是普通方法，使用requests或httpx.get
                import requests
                response = requests.get(url, timeout=60.0)
                response.raise_for_status()
                return response.content

            # 是我们自己的OSS，从OSS链接中提取object_key
            parts = url.split(f'.{endpoint_domain}/')
            if len(parts) > 1:
                object_key = unquote(parts[1].split('?')[0])  # 移除查询参数并解码
            else:
                 # 尝试另一种格式
                 parts = url.split(f'/{self.bucket_name}/') # path style
                 if len(parts) > 1:
                      object_key = unquote(parts[1].split('?')[0])
                 else:
                      raise Exception(f"无法从URL提取object_key: {url}")
        else:
            # 直接是object_key
            object_key = url

        # 从OSS下载文件
        self._ensure_configured()
        result = self.bucket.get_object(object_key)
        file_content = result.read()

        return file_content

