"""
百川智能 Baichuan-M3-Plus API 服务
用于获取基础健康建议和治疗方案
"""
import json
import hashlib
import logging
import re
from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings

logger = logging.getLogger("healthy_rag")


def _build_api_key_fingerprint(api_key: Optional[str]) -> str:
    """构造 API Key 的安全指纹字符串（不泄露完整密钥）。

    Args:
        api_key: 原始 API Key

    Returns:
        指纹信息字符串（sha256 截断 + 后 4 位），或缺失/空白标识。
    """
    if api_key is None:
        return "missing"

    api_key_str = api_key.strip()
    if not api_key_str:
        return "blank"

    last4 = api_key_str[-4:] if len(api_key_str) >= 4 else api_key_str
    digest_prefix = hashlib.sha256(api_key_str.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest_prefix}... last4:{last4}"


class BaichuanService:
    """百川智能 API 服务类"""
    
    def __init__(self) -> None:
        self.api_key: Optional[str] = settings.BAICHUAN_API_KEY
        self.base_url = settings.BAICHUAN_BASE_URL
        self.model = settings.BAICHUAN_MODEL
        self.timeout = settings.BAICHUAN_TIMEOUT

        logger.info(
            "Baichuan client configured base_url=%s model=%s api_key_fingerprint=%s",
            self.base_url,
            self.model,
            _build_api_key_fingerprint(self.api_key),
        )
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def get_health_suggestions(
        self,
        user_info: str,
        track: str,
        qa_pairs: str,
        temperature: float = 0.3
    ) -> Optional[str]:
        """
        调用百川 Baichuan-M3-Plus 模型获取健康建议
        
        Args:
            user_info: 用户基本信息
            track: 健康赛道
            qa_pairs: 问卷问答内容
            temperature: 温度参数，控制输出多样性
        
        Returns:
            健康建议文本，失败返回 None
        """
        if not self.api_key:
            logger.warning("Baichuan API Key not configured, skipping health suggestions")
            return None
        
        try:
            # 构建完整的用户消息（百川不支持 system role，需要将指令合并到用户消息中）
            full_user_message = f"""您是一名专业的健康顾问。根据用户的健康问卷回答，请提供基础的健康建议和治疗方案。

请提供以下内容：
1. 健康状况分析
2. 风险评估
3. 基础治疗建议
4. 生活方式调整建议

请用专业但易懂的语言回答，避免使用过于专业的医学术语。

---

用户信息：{user_info}
健康赛道：{track}

问卷内容：
{qa_pairs}

---

请根据以上信息，提供专业的健康评估和建议。"""

            # 构建请求
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": full_user_message}
                ],
                "temperature": temperature,
                "stream": False,
                "max_tokens": 2048
            }
            
            logger.info(f"Calling Baichuan API for health suggestions (model: {self.model})...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                # 提取回复内容
                content = result["choices"][0]["message"]["content"].strip()
                
                # 提取 thinking 和 grounding 信息（如果有）
                thinking = result["choices"][0].get("thinking")
                grounding = result["choices"][0].get("grounding")
                
                # 记录使用情况
                usage = result.get("usage", {})
                logger.info(
                    f"Baichuan API call successful. "
                    f"Tokens: {usage.get('total_tokens', 0)} "
                    f"(prompt: {usage.get('prompt_tokens', 0)}, "
                    f"completion: {usage.get('completion_tokens', 0)})"
                )
                
                # 如果有 thinking 信息，记录日志
                if thinking:
                    logger.info(f"Baichuan thinking status: {thinking.get('status')}")
                
                # 如果有 grounding 证据，记录日志
                if grounding and grounding.get("evidence"):
                    evidence_count = len(grounding["evidence"])
                    logger.info(f"Baichuan provided {evidence_count} evidence references")
                
                return content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Baichuan API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Baichuan API timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Baichuan API call failed: {str(e)}")
            return None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def extract_tags_from_ocr_and_questionnaire(
        self,
        ocr_text: str,
        questionnaire_text: str,
        temperature: float = 0.1
    ) -> Optional[List[str]]:
        """
        从OCR识别的体检报告文本和问卷回答中提取标准化标签
        
        Args:
            ocr_text: OCR识别的原始体检报告文本
            questionnaire_text: 用户的问卷回答内容
            temperature: 温度参数，低温度确保稳定输出
        
        Returns:
            标准化标签列表，失败返回空列表
        """
        if not self.api_key:
            logger.warning("Baichuan API Key not configured, skipping tag extraction")
            return []
        
        # 使用 docs/ocr解析.txt 中的 prompt，并结合问卷信息
        prompt = f"""Role (角色设定)
你是一名 资深医学数据分析师，专长是综合分析体检报告和健康问卷，提取异常健康指标。
你的核心任务是：从体检报告的OCR文本和用户的问卷回答中，精准提取出 异常指标、症状和关键诊断结论，并将它们转化为 标准化的风险标签。

Input Data (输入数据)

【体检报告OCR文本】
{ocr_text}

【用户问卷回答】
{questionnaire_text}

Task Workflow (工作流)
请按以下步骤处理：
1. 降噪与纠错 (Clean & Correct)：
  - 忽略医院名称、科室、日期、页码等非医疗信息。
  - 修正常见的 OCR 错误（例如：将 "l00" 修正为 "100"，"High" 修正为 "High"）。
2. 异常识别 (Anomaly Detection)：
  - 从体检报告中：寻找明确的异常标记，如：↑, ↓, +, 阳性, Positive, H (High), L (Low)。
  - 从体检报告中：寻找包含"结节"、"囊肿"、"增生"、"肥大"、"炎症"等描述的诊断结论。
  - 从问卷回答中：提取用户提到的症状、不适、疾病史等异常健康状况。
3. 标签归一化 (Normalization) - 核心步骤：
  - **必须严格使用以下标准标签库中的词汇**（这是为了匹配后端的推荐规则）
  - 如果识别出的异常不在标签库中，请选择最接近的标签，或者不输出
  
  **标准标签库（按健康赛道分类）：**
  
  【神经系统】
  - 入睡困难, 失眠, 皮质醇高, GABA低, 早醒, 多梦
  - 焦感, 压力过大
  
  【消化系统】
  - 转氨酶高, 便秘, 排便困难, 肠道菌群, 口臭, 胃痛
  - 腹胀, 消化不良, 嗳气或嗳杆
  
  【免疫与出血】
  - 白细胞高, 淋巴异常, 盗血, 反复感冒
  - 过敏, 鼻塞, 湿疹, IgE高
  
  【心血管】
  - 血脂异常, 甘油三酯高, 胆固醇高, LDL-C高, 轻度血脂高
  - 血压略高, 油脂饮食
  
  【内分泌】
  - TSH异常, 甲状腺结节, 皮质醇异常, 怕冷, 代谢慢
  - 月经不调, 痛经, PCOS, 慢经或波动
  
  【骨骼与代谢】
  - 骨密度低, 骨质流失, 关节疼痛, 骨折史
  - 尿酸高, 痛风, 肥胖
  
  【皮肤】
  - 敏感, 松弛, 法令纹, 皮肤流失
  - 激素脸, 痘敏, 真菌感染, 皮炎

Constraints (硬性约束)
1. **只提取异常项**： 
   - 正常的指标（如"正常"、"阴性"、"未见异常"）不要输出
   - 健康的症状（如"无不适"、"睡眠良好"）不要输出
   
2. **严格使用标签库**：
   - 只能输出上述标准标签库中的词汇
   - 不要自创标签，不要使用近义词
   - 例如：识别到"睡不着"应输出"失眠"，识别到"过敏性鼻炎"应输出"过敏"和"鼻塞"
   
3. **综合两个来源**： 
   - 同时分析体检报告和问卷回答
   - 体检报告侧重客观指标（如血脂高、TSH异常）
   - 问卷回答侧重主观症状（如失眠、焦虑、鼻塞）
   
4. **智能映射与过滤**：
   - **正常抗体不提取**：体检报告中的"乙型肝炎表面抗体阳性/升高"是正常的保护性抗体，绝对不要提取
   - **异常抗原才提取**：体检报告中的"乙型肝炎表面抗原阳性"才是异常，应提取相关标签
   - **问卷症状映射**：
     * "经常鼻塞" → "鼻塞"
     * "容易过敏" → "过敏"
     * "睡不着" → "失眠"
     * "入睡难" → "入睡困难"
   - **无法映射的不提取**：如果问卷中的症状无法映射到标签库中的任何标签，不要输出
     * 例如："感觉没精神"无法准确映射到标签库中的标签，不要直接输出原文
   
5. **严禁臆造**： 
   - 没有明确提到的数据不要编造
   - 不确定的异常不要输出
   
6. **格式严格**： 
   - 直接输出JSON数组，不要添加任何解释文字
   - 不要输出Markdown代码块标记（如 ```json）

Output Format (输出格式)
请直接输出一个JSON数组，只包含标签，不要任何额外文字。

**示例1（体检报告+问卷）：**
输入：
- 体检报告：TSH 8.5 ↑, 甲状腺结节 TI-RADS 3级, 总胆固醇 6.2 ↑
- 问卷：经常失眠，入睡困难，鼻塞严重

输出：
["TSH异常", "甲状腺结节", "胆固醇高", "失眠", "入睡困难", "鼻塞"]

**示例2（仅问卷）：**
输入：
- 体检报告：无
- 问卷：最近压力大，经常焦虑，偶尔胃痛

输出：
["压力过大", "焦感", "胃痛"]

**示例3（仅体检报告）：**
输入：
- 体检报告：尿酸 480 ↑, 骨密度 T值 -2.8
- 问卷：无

输出：
["尿酸高", "骨密度低"]

**示例4（无异常）：**
输入：
- 体检报告：各项指标正常
- 问卷：身体健康，无不适

输出：
[]

注意：
1. 只输出JSON数组，不要前后添加任何文字
2. 标签必须来自标准标签库
3. 同时包含体检报告的异常指标和问卷中的症状"""

        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "stream": False,
                "max_tokens": 1024
            }
            
            logger.info(f"Calling Baichuan API to extract tags from OCR text and questionnaire...")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # 尝试解析 JSON
                import json
                import re
                try:
                    # 移除可能的 markdown 代码块标记
                    content = content.replace("```json", "").replace("```", "").strip()
                    
                    # 替换中文引号为英文引号
                    content = content.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
                    
                    # 尝试提取第一个JSON数组（百川可能在JSON后面添加额外说明）
                    # 匹配 [ ... ] 格式
                    json_match = re.search(r'\[.*?\]', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        tags = json.loads(json_str)
                        
                        if isinstance(tags, list):
                            # 后处理：验证标签是否在标准标签库中
                            valid_tags = self._validate_tags(tags)
                            logger.info(f"Extracted {len(tags)} tags, validated {len(valid_tags)} tags: {valid_tags}")
                            if len(valid_tags) < len(tags):
                                logger.warning(f"Filtered out invalid tags: {set(tags) - set(valid_tags)}")
                            return valid_tags
                        else:
                            logger.warning(f"Baichuan returned non-list format: {json_str}")
                            return []
                    else:
                        logger.warning(f"No JSON array found in Baichuan response: {content[:200]}")
                        return []
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Baichuan response as JSON: {content[:200]}")
                    logger.error(f"JSON decode error details: {str(e)}")
                    return []
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Baichuan API HTTP error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Baichuan tag extraction failed: {str(e)}")
            return []

    def _validate_tags(self, tags: List[str]) -> List[str]:
        """
        验证标签是否在标准标签库中
        
        Args:
            tags: 待验证的标签列表
        
        Returns:
            验证后的标签列表（只包含标签库中的标签）
        """
        # 标准标签库（与提示词中的标签库一致）
        STANDARD_TAGS = {
            # 神经系统
            "入睡困难", "失眠", "皮质醇高", "GABA低", "早醒", "多梦",
            "焦感", "压力过大",
            # 消化系统
            "转氨酶高", "便秘", "排便困难", "肠道菌群", "口臭", "胃痛",
            "腹胀", "消化不良", "嗳气或嗳杆",
            # 免疫与出血
            "白细胞高", "淋巴异常", "盗血", "反复感冒",
            "过敏", "鼻塞", "湿疹", "IgE高",
            # 心血管
            "血脂异常", "甘油三酯高", "胆固醇高", "LDL-C高", "轻度血脂高",
            "血压略高", "油脂饮食",
            # 内分泌
            "TSH异常", "甲状腺结节", "皮质醇异常", "怕冷", "代谢慢",
            "月经不调", "痛经", "PCOS", "慢经或波动",
            # 骨骼与代谢
            "骨密度低", "骨质流失", "关节疼痛", "骨折史",
            "尿酸高", "痛风", "肥胖",
            # 皮肤
            "敏感", "松弛", "法令纹", "皮肤流失",
            "激素脸", "痘敏", "真菌感染", "皮炎"
        }
        
        # 过滤出标签库中的标签
        valid_tags = [tag for tag in tags if tag in STANDARD_TAGS]
        
        return valid_tags

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
    )
    async def generate_json_by_prompt(
        self,
        *,
        prompt: str,
        input_text: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        使用“外部提供的prompt”（如 update/update.md）生成 JSON 文本。

        Notes:
            - 百川接口在本项目中按“合并到 user message”方式使用。
            - 返回原始字符串；解析与修复由上层负责。
        """
        if not self.api_key:
            raise ValueError("Baichuan API Key not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        full_user_message = f"""{prompt}

---

【输入数据】
{input_text}

---

只输出 JSON："""

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": full_user_message}],
            "temperature": temperature,
            "stream": False,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip()

    async def extract_tags_from_ocr(
        self,
        ocr_text: str,
        temperature: float = 0.1
    ) -> Optional[List[str]]:
        """
        从OCR识别的体检报告文本中提取标签（兼容旧接口）
        
        实际调用 extract_tags_from_ocr_and_questionnaire，但问卷文本为空
        """
        return await self.extract_tags_from_ocr_and_questionnaire(
            ocr_text=ocr_text,
            questionnaire_text="",
            temperature=temperature
        )


# 单例实例
baichuan_service = BaichuanService()

