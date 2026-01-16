"""
Qwen VL 服务
用于通过 qwen3-vl-plus 模型解析图片和PDF文件中的文字内容
"""
import httpx
import logging
from typing import Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)


class QwenVLService:
    """阿里云通义千问 VL 视觉理解服务"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.base_url = settings.QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = "qwen3-vl-plus-2025-12-19"
        self.timeout = settings.GEMINI_TIMEOUT or 300  # 使用 Gemini 的超时设置

    async def parse_file_content(self, file_url: str, prompt: Optional[str] = None) -> str:
        """
        解析文件内容（图片或PDF）
        
        Args:
            file_url: 文件的URL地址（必须是可公开访问的URL）
            prompt: 可选的提示词，默认为提取文本内容
        
        Returns:
            解析后的文本内容
        
        Raises:
            Exception: API调用失败时抛出异常
        """
        if not self.api_key:
            raise Exception("Qwen VL API key 未配置，请在 .env 中设置 DASHSCOPE_API_KEY")

        # 默认提示词：提取文档中的所有文字内容
        if prompt is None:
            prompt = """请仔细识别这张图片中的所有文字内容，包括：
1. 标题、栏目名称
2. 表格数据（包括表头和数值）
3. 检查项目名称和结果
4. 任何医学诊断或建议
5. 参考范围和单位

请按照原文的排版结构输出，保持表格和层级关系清晰。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": file_url}
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 4096,  # 增加输出长度以支持长文档
            "temperature": 0.1,  # 低温度确保准确性
        }

        try:
            logger.info(f"调用 Qwen VL 解析文件: {file_url[:50]}...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"Qwen VL 解析成功，内容长度: {len(content)}")
                    return content
                else:
                    raise Exception(f"Qwen VL API 返回格式错误: {result}")

        except httpx.HTTPStatusError as e:
            error_msg = f"Qwen VL API HTTP 错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        except httpx.TimeoutException:
            error_msg = "Qwen VL API 请求超时"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        except Exception as e:
            error_msg = f"Qwen VL 解析失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def parse_medical_report(self, file_url: str) -> str:
        """
        专门用于解析医疗体检报告的方法
        
        Args:
            file_url: 体检报告文件URL
        
        Returns:
            解析后的文本内容
        """
        medical_prompt = """这是一份医疗体检报告，请仔细识别并提取以下信息：

1. **基本信息**：姓名、性别、年龄、体检日期
2. **检查项目和结果**：
   - 所有检查项目名称
   - 检测数值和单位
   - 参考范围
   - 异常标记（↑ ↓ H L + - 阳性 阴性等）
3. **诊断结论**：医生的诊断意见、建议、备注
4. **异常项目**：特别标注所有异常的项目

请按照原报告的结构和顺序输出，确保数据准确完整。"""

        return await self.parse_file_content(file_url, medical_prompt)

    async def parse_multiple_images(self, file_urls: list) -> str:
        """
        批量解析多张体检报告图片（一次调用大模型）
        
        Args:
            file_urls: 多个体检报告文件URL列表
        
        Returns:
            合并后的解析文本内容
        """
        if not self.api_key:
            raise Exception("Qwen VL API key 未配置，请在 .env 中设置 DASHSCOPE_API_KEY")

        medical_prompt = f"""这是 {len(file_urls)} 张医疗体检报告图片，请仔细识别并提取所有图片中的信息：

1. **基本信息**：姓名、性别、年龄、体检日期
2. **检查项目和结果**：
   - 所有检查项目名称
   - 检测数值和单位
   - 参考范围
   - 异常标记（↑ ↓ H L + - 阳性 阴性等）
3. **诊断结论**：医生的诊断意见、建议、备注
4. **异常项目**：特别标注所有异常的项目

请合并所有图片的信息，按照原报告的结构和顺序输出，确保数据准确完整。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 构建多图片的content
        content = []
        for file_url in file_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": file_url}
            })
        content.append({
            "type": "text",
            "text": medical_prompt
        })

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        }

        try:
            logger.info(f"调用 Qwen VL 批量解析 {len(file_urls)} 张图片...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"Qwen VL 批量解析成功，内容长度: {len(content)}")
                    return content
                else:
                    raise Exception(f"Qwen VL API 返回格式错误: {result}")

        except httpx.HTTPStatusError as e:
            error_msg = f"Qwen VL API HTTP 错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        except httpx.TimeoutException:
            error_msg = "Qwen VL API 请求超时"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        except Exception as e:
            error_msg = f"Qwen VL 批量解析失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


# 创建全局实例
qwen_vl_service = QwenVLService()

