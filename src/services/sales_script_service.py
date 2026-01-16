"""销售助手：AI 推荐话术生成服务（DeepSeek 高思考模型）。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.tables import Message, Report, Session, User
from src.models.tables.chat import SalesScript
from src.services.llm_service import llm_service
from src.services.product_recommendation_service import product_recommendation_service

logger = logging.getLogger(__name__)


class ReportNotFoundError(Exception):
    """报告不存在异常（通常表示尚未生成报告，无法保存与报告绑定的数据）。"""


@dataclass(frozen=True)
class SalesScriptVariables:
    """话术变量集合（用于模板填充与高亮定位）。"""

    salutation: str
    pain_point: str
    score: Optional[int]
    track: str
    core_ingredient_name: str
    search_keyword: str
    buying_tip: str


def _normalize_gender(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = str(raw).strip()
    if '女' in value:
        return '女'
    if '男' in value:
        return '男'
    return None


def _extract_age_gender(meta_data: Any) -> Tuple[Optional[int], Optional[str]]:
    if not isinstance(meta_data, dict):
        return None, None

    age_raw = meta_data.get('age') or meta_data.get('年龄')
    gender_raw = meta_data.get('gender') or meta_data.get('sex') or meta_data.get('性别')

    age: Optional[int] = None
    try:
        if age_raw is not None and str(age_raw).strip():
            age = int(str(age_raw).strip())
    except Exception:
        age = None

    gender = _normalize_gender(gender_raw)
    return age, gender


def _infer_age_gender_from_text(text: str) -> Tuple[Optional[int], Optional[str]]:
    """从自由文本中粗略推断年龄/性别（尽量稳健，不做过度猜测）。"""
    if not text:
        return None, None

    age = None
    gender = None

    # 年龄：匹配 “33岁”“ 33 岁”
    match = re.search(r'(\d{1,3})\s*岁', text)
    if match:
        try:
            age = int(match.group(1))
        except Exception:
            age = None

    # 性别：匹配 “男”“女”，避免误伤（例如“男女”“男科”等）
    if re.search(r'(^|[\s，,;；。])女($|[\s，,;；。])', text):
        gender = '女'
    elif re.search(r'(^|[\s，,;；。])男($|[\s，,;；。])', text):
        gender = '男'
    else:
        # 兼容常见格式：如“40 女 胃口不好”
        if '女' in text and '男性' not in text:
            gender = '女'
        elif '男' in text and '女性' not in text:
            gender = '男'

    return age, gender


def _map_salutation(age: Optional[int], gender: Optional[str]) -> str:
    """
    PRD 映射规则（简化版）：
    - 女 + <30: 亲
    - 女 + 30-50: 女士
    - 女 + >50: 阿姨
    - 男 + <35: 帅哥
    - 男 + >=35: 先生
    - 未知：您
    """
    if gender == '女':
        if age is None:
            return '女士'
        if age < 30:
            return '亲'
        if age <= 50:
            return '女士'
        return '阿姨'
    if gender == '男':
        if age is None:
            return '先生'
        if age < 35:
            return '帅哥'
        return '先生'
    return '您'


def _extract_pain_point(messages: List[Message]) -> str:
    for msg in messages:
        if msg.role == 'user' and (msg.content or '').strip():
            return (msg.content or '').strip()
    return ''


def _extract_report_score_track(report: Optional[Report]) -> Tuple[Optional[int], str]:
    if not report:
        return None, '未知赛道'

    score = report.score
    track: Optional[str] = None
    try:
        content = report.content or {}
        if isinstance(content, dict):
            baichuan_json = content.get('baichuan_json') or {}
            if isinstance(baichuan_json, dict):
                if score is None:
                    score_val = baichuan_json.get('score')
                    if score_val is not None:
                        score = int(score_val)
                track_val = baichuan_json.get('track')
                if isinstance(track_val, str) and track_val.strip():
                    track = track_val.strip()
    except Exception:
        # 只读兜底
        pass

    if not track:
        # 兼容：报告表上通常没有 track 字段，退回到 session.meta_data
        track = '未知赛道'

    return score, track


def _safe_json_extract(text: str) -> Dict[str, Any]:
    """
    从 LLM 输出中抽取 JSON。
    允许模型输出多余文字，取第一个 {...} 块尝试解析。
    """
    text = (text or '').strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        raise ValueError('LLM 输出不包含 JSON 对象')
    raw = match.group(0)
    return json.loads(raw)


def _build_highlights(text: str, targets: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    targets: [(substring, kind)]
    返回按出现顺序的 span 列表。
    """
    spans: List[Dict[str, Any]] = []
    for sub, kind in targets:
        if not sub:
            continue
        start = text.find(sub)
        if start == -1:
            continue
        spans.append(
            {
                'text': sub,
                'start': start,
                'end': start + len(sub),
                'kind': kind,
            }
        )
    spans.sort(key=lambda x: x['start'])
    return spans


class SalesScriptService:
    """生成 AI 推荐话术（搜索导向三段式）。"""

    async def generate_sales_script(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        tone: str,
        channel: Optional[str],
        channel_source: Optional[str],
        recommendation_rule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成三段式话术（Step1/2/3），并按产品要求输出高亮 spans。

        Args:
            db: 数据库会话
            session_id: 会话ID
            tone: 'expert' | 'friend'
            channel: 渠道标识（可扩展）
            channel_source: 渠道来源说明（可扩展）
            recommendation_rule_id: 指定规则ID（可选）

        Returns:
            dict: 可 JSON 序列化的响应数据
        """
        result = await db.execute(
            select(Session, Report, User)
            .join(User, Session.user_id == User.id)
            .outerjoin(Report, Session.id == Report.session_id)
            .where(Session.id == session_id)
        )
        row = result.first()
        if not row:
            raise ValueError('Session not found')

        session, report, user = row

        msgs_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = msgs_result.scalars().all()

        age, gender = _extract_age_gender(session.meta_data)
        if age is None or gender is None:
            combined_user_text = '；'.join(
                [(m.content or '').strip() for m in messages if m.role == 'user']
            )
            inferred_age, inferred_gender = _infer_age_gender_from_text(
                combined_user_text
            )
            age = age if age is not None else inferred_age
            gender = gender if gender is not None else inferred_gender
        salutation = _map_salutation(age, gender)
        pain_point = _extract_pain_point(messages)

        score, track = _extract_report_score_track(report)

        # 获取推荐规则（优先使用现有推荐服务排序结果）
        recommendations = await product_recommendation_service.get_recommended_products_by_session(
            db, session_id
        )
        chosen: Optional[Dict[str, Any]] = None
        if recommendation_rule_id:
            for item in recommendations:
                if item.get('rule_id') == recommendation_rule_id:
                    chosen = item
                    break
        if not chosen:
            chosen = recommendations[0] if recommendations else None

        core_ingredient_name = ''
        search_keyword = ''
        buying_tip = ''
        if chosen:
            core_ingredient_name = (chosen.get('core_ingredient_name') or '').strip()
            search_keyword = (chosen.get('toc_search_query') or '').strip()
            buying_tip = (chosen.get('buying_tip') or '').strip()

        variables = SalesScriptVariables(
            salutation=salutation,
            pain_point=pain_point or '近期困扰',
            score=score,
            track=track or '未知赛道',
            core_ingredient_name=core_ingredient_name or '核心营养成分',
            search_keyword=search_keyword or '关键词',
            buying_tip=buying_tip or '',
        )

        llm_payload = self._build_llm_prompt(variables=variables, tone=tone)
        llm_text = await llm_service.deepseek_completion(
            messages=[{'role': 'user', 'content': llm_payload}],
            system_prompt=self._system_prompt(),
            model=settings.DEEP_SEEK_MODEL_REASONER,
            temperature=None,
        )

        try:
            llm_json = _safe_json_extract(llm_text)
            step1 = str(llm_json.get('step1', '')).strip()
            step2 = str(llm_json.get('step2', '')).strip()
            step3 = str(llm_json.get('step3', '')).strip()
            keyword = str(llm_json.get('search_keyword', '')).strip() or variables.search_keyword
        except Exception as exc:
            logger.warning('LLM JSON 解析失败，回退到模板生成: %s', exc)
            step1, step2, step3, keyword = self._fallback_template(variables=variables, tone=tone)

        # 高亮规则（按你的要求）
        step1_highlights = _build_highlights(
            step1,
            [
                (variables.salutation, 'salutation'),
                (str(variables.score) if variables.score is not None else '', 'score'),
            ],
        )
        step2_highlights = _build_highlights(
            step2,
            [(variables.core_ingredient_name, 'ingredient')],
        )
        step3_highlights = _build_highlights(
            step3,
            [(keyword, 'search_keyword')],
        )

        return {
            'session_id': session_id,
            'tone': tone,
            'channel': channel,
            'channel_source': channel_source,
            'steps': [
                {
                    'step': 'step1',
                    'title': 'Step 1: 破冰切入',
                    'text': step1,
                    'highlights': step1_highlights,
                },
                {
                    'step': 'step2',
                    'title': 'Step 2: 方案建议',
                    'text': step2,
                    'highlights': step2_highlights,
                },
                {
                    'step': 'step3',
                    'title': 'Step 3: 选购指引',
                    'text': step3,
                    'highlights': step3_highlights,
                },
            ],
            'search_keyword': keyword,
            'variables': {
                'salutation': variables.salutation,
                'pain_point': variables.pain_point,
                'score': variables.score,
                'track': variables.track,
                'core_ingredient_name': variables.core_ingredient_name,
                'search_keyword': keyword,
                'buying_tip': variables.buying_tip,
                'age': age,
                'gender': gender,
            },
        }

    async def get_saved_sales_script(
        self,
        db: AsyncSession,
        *,
        session_id: int,
    ) -> Optional[SalesScript]:
        """读取已保存话术（同一报告唯一一条；如不存在返回 None）。"""
        report_id = await self._get_report_id_by_session(db, session_id=session_id)
        if report_id is None:
            return None
        result = await db.execute(
            select(SalesScript).where(SalesScript.report_id == report_id)
        )
        return result.scalar_one_or_none()

    async def build_saved_sales_script_response(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        tone_default: str = "expert",
        channel_default: str = "wechat_private",
    ) -> Dict[str, Any]:
        """
        构建“已保存话术”的返回结构（不调用大模型）。

        若未保存，返回空结构（steps=[]），由调用方决定是否继续调用 generate 接口。
        """
        saved = await self.get_saved_sales_script(db, session_id=session_id)

        if not saved:
            return {
                "session_id": session_id,
                "tone": tone_default,
                "channel": channel_default,
                "channel_source": None,
                "is_saved": False,
                "steps": [],
                "search_keyword": "",
                "variables": {},
            }

        # 读取 session/report/messages，用于计算称呼与分数（无需 LLM）
        result = await db.execute(
            select(Session, Report, User)
            .join(User, Session.user_id == User.id)
            .outerjoin(Report, Session.id == Report.session_id)
            .where(Session.id == session_id)
        )
        row = result.first()
        if not row:
            raise ValueError("Session not found")

        session, report, _user = row

        msgs_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = msgs_result.scalars().all()

        age, gender = _extract_age_gender(session.meta_data)
        if age is None or gender is None:
            combined_user_text = "；".join(
                [(m.content or "").strip() for m in messages if m.role == "user"]
            )
            inferred_age, inferred_gender = _infer_age_gender_from_text(
                combined_user_text
            )
            age = age if age is not None else inferred_age
            gender = gender if gender is not None else inferred_gender

        salutation = _map_salutation(age, gender)
        score, track = _extract_report_score_track(report)

        keyword = (saved.search_keyword or "").strip()
        ingredient = (saved.core_ingredient_name or "").strip()

        step1_text = saved.step1_text
        step2_text = saved.step2_text
        step3_text = saved.step3_text

        return {
            "session_id": session_id,
            "tone": saved.tone or tone_default,
            "channel": saved.channel or channel_default,
            "channel_source": saved.channel_source,
            "is_saved": True,
            "steps": [
                {
                    "step": "step1",
                    "title": "Step 1: 破冰切入",
                    "text": step1_text,
                    "highlights": _build_highlights(
                        step1_text,
                        [
                            (salutation, "salutation"),
                            (str(score) if score is not None else "", "score"),
                        ],
                    ),
                },
                {
                    "step": "step2",
                    "title": "Step 2: 方案建议",
                    "text": step2_text,
                    "highlights": _build_highlights(
                        step2_text, [(ingredient, "ingredient")]
                    ),
                },
                {
                    "step": "step3",
                    "title": "Step 3: 选购指引",
                    "text": step3_text,
                    "highlights": _build_highlights(
                        step3_text, [(keyword, "search_keyword")]
                    ),
                },
            ],
            "search_keyword": keyword,
            "variables": {
                "salutation": salutation,
                "score": score,
                "track": track,
                "core_ingredient_name": ingredient,
                "search_keyword": keyword,
                "age": age,
                "gender": gender,
            },
        }

    async def save_sales_script(
        self,
        db: AsyncSession,
        *,
        session_id: int,
        tone: str,
        channel: str,
        channel_source: Optional[str],
        step1_text: str,
        step2_text: str,
        step3_text: str,
        search_keyword: str,
        core_ingredient_name: Optional[str],
    ) -> SalesScript:
        """保存编辑后的话术（upsert）。"""
        report_id = await self._get_report_id_by_session(db, session_id=session_id)
        if report_id is None:
            raise ReportNotFoundError(
                "Report not found. Please generate report first."
            )

        existing = await self.get_saved_sales_script(db, session_id=session_id)
        if existing:
            existing.channel_source = channel_source
            existing.step1_text = step1_text
            existing.step2_text = step2_text
            existing.step3_text = step3_text
            existing.search_keyword = search_keyword
            existing.core_ingredient_name = core_ingredient_name
            existing.tone = tone
            existing.channel = channel
            existing.report_id = report_id
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        script = SalesScript(
            session_id=session_id,
            report_id=report_id,
            tone=tone,
            channel=channel,
            channel_source=channel_source,
            step1_text=step1_text,
            step2_text=step2_text,
            step3_text=step3_text,
            search_keyword=search_keyword,
            core_ingredient_name=core_ingredient_name,
        )
        db.add(script)
        await db.commit()
        await db.refresh(script)
        return script

    async def _get_report_id_by_session(
        self, db: AsyncSession, *, session_id: int
    ) -> Optional[int]:
        """根据 session_id 获取报告ID（用于“按报告存话术”）。"""
        result = await db.execute(
            select(Report.id).where(Report.session_id == session_id)
        )
        return result.scalar_one_or_none()

    def _system_prompt(self) -> str:
        # 该系统提示词对齐 PRD：「AI 推荐话术生成逻辑 (PRD)」
        # 重点约束：
        # - 三段式严格遵守 Hook / Solution / Action
        # - 不卖 SKU：不出现品牌/商品名/价格/折扣，仅引导“搜索关键词 + 避坑”
        # - 输出必须为严格 JSON（方便前端渲染与高亮）
        return (
            "Role (角色设定)\n"
            "你是一名经验丰富的【健康管理顾问】。你的任务是根据用户的健康评估报告，"
            "生成一套高转化率的“三段式”跟单话术。\n\n"
            "Context (业务背景)\n"
            "我们要为用户提供个性化的营养干预方案。\n"
            "关键规则：我们不直接售卖商品，而是作为中立专家，推荐用户去电商平台（淘宝/京东）"
            "搜索特定的【优质成分关键词】，并提供选购避坑指南。\n\n"
            "Tone Configuration (语气风格)\n"
            "当前设定的语气是：{{tone}}\n"
            "- If 专业专家：语气客观、冷静、权威。多用“数据显示”、“临床建议”。关键词：专业、高效、科学。\n"
            "- If 贴心闺蜜：语气温暖、共情、活泼。多用“亲爱的”、“抱抱”、“听我的”。关键词：心疼、陪伴、种草。\n\n"
            "Task Flow (生成逻辑 - 必须严格遵守三段式)\n"
            "Step 1: Hook (破冰与痛点切入)\n"
            "- 逻辑：使用 user_title 称呼用户 -> 提及 track (赛道) 和 score (分数) -> "
            "将 symptoms (症状) 解释为身体的“求救信号”。\n"
            "- 目标：建立信任，制造适度的健康焦虑。\n\n"
            "Step 2: Solution (方案与原理)\n"
            "- 逻辑：引出 recommend_ingredient (推荐成分) -> 简述其起效原理 -> 强调为什么要补这个。\n"
            "- 目标：树立专业度，给出解决方案。\n\n"
            "Step 3: Action (搜索指引与避坑)\n"
            "- 逻辑：严禁提及具体价格或折扣！\n"
            "- 话术核心：引导用户去电商平台搜索 search_keyword。\n"
            "- 关键动作：必须自然地融入 buying_tip (选购指引)，告诉用户如何挑选，体现专家的“避坑价值”。\n"
            "  注意：前端可能会把“专家提示”作为独立UI模块渲染，因此不要强制使用固定前缀或表情。\n\n"
            "输出格式要求（必须遵守）\n"
            "1) 只输出严格 JSON，不要输出任何额外文本。\n"
            "2) JSON 字段固定为：step1, step2, step3, search_keyword。\n"
            "3) 严禁出现任何品牌名、SKU、价格、折扣、购买链接。\n"
        )

    def _build_llm_prompt(self, *, variables: SalesScriptVariables, tone: str) -> str:
        tone_desc = "专业专家" if tone == "expert" else "贴心闺蜜"
        score_text = str(variables.score) if variables.score is not None else "N/A"
        # user prompt：把变量映射为 PRD 使用的字段名，减少歧义
        return (
            "请将下列变量填充到系统提示词的三段式结构中，生成严格 JSON。\n\n"
            f"tone: {tone_desc}\n"
            f"user_title: {variables.salutation}\n"
            f"track: {variables.track}\n"
            f"score: {score_text}\n"
            f"symptoms: {variables.pain_point}\n"
            f"recommend_ingredient: {variables.core_ingredient_name}\n"
            f"search_keyword: {variables.search_keyword}\n"
            f"buying_tip: {variables.buying_tip}\n\n"
            "输出 JSON schema（必须严格遵守）：\n"
            "{\n"
            '  "step1": "string",\n'
            '  "step2": "string",\n'
            '  "step3": "string",\n'
            '  "search_keyword": "string"\n'
            "}\n\n"
            "硬性检查（必须满足）：\n"
            "1) step1 必须同时包含 user_title、track、score、symptoms；\n"
            "2) step2 必须包含 recommend_ingredient，并用一句话解释其起效原理；\n"
            "3) step3 必须包含 search_keyword，并自然融入 buying_tip（可作为独立一句/一段建议，不强制固定前缀）；\n"
            "4) 全程严禁出现品牌名、SKU、价格、折扣、购买链接。\n"
        )

    def _fallback_template(
        self, *, variables: SalesScriptVariables, tone: str
    ) -> Tuple[str, str, str, str]:
        score_text = str(variables.score) if variables.score is not None else 'N/A'
        if tone == 'friend':
            step1 = (
                f'{variables.salutation}，我看您的{variables.track}评分大概是{score_text}分，'
                f'您提到的“{variables.pain_point}”，确实是身体在提醒要重视了。'
            )
        else:
            step1 = (
                f'{variables.salutation}，您的{variables.track}评分是{score_text}分。'
                f'您提到的“{variables.pain_point}”，其实是身体发出的警报。'
            )

        step2 = (
            f'针对这种情况，建议优先补充【{variables.core_ingredient_name}】。'
            '它能从源头进行干预，比盲目尝试更有针对性。'
        )

        tip = variables.buying_tip.strip()
        tip_text = tip if tip else "优先看配料表与核心含量。"
        keyword = variables.search_keyword
        step3 = (
            f'建议您去京东或淘宝，直接搜索关键词【{keyword}】。\n'
            f'选购时注意：{tip_text}'
        )
        return step1, step2, step3, keyword


sales_script_service = SalesScriptService()


