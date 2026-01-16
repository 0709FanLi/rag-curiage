from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from typing import List
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from datetime import timezone

from src.api.dependencies import get_db, get_current_user, get_dashboard_cache_service
from src.models.tables import ChannelSourceOption, Message, Report, Session, User, UserProfile
from src.utils.logging import logger
from src.schemas.admin import (
    DashboardMetricsResponse,
    DashboardFunnelResponse,
    DashboardDistributionResponse,
    RecordListResponse,
    RecordListItem,
    RecordDetailResponse,
    RecordMessageItem,
    FunnelStep,
    TrackDistributionItem
)
from src.schemas.sales_script import (
    SalesScriptConfigResponse,
    SalesScriptGenerateRequest,
    SalesScriptGenerateResponse,
    SalesScriptSaveRequest,
)
from src.schemas.channel_source import (
    ChannelSourceConfigResponse,
    UpdateChannelSourceRequest,
    UpdateChannelSourceResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


CHANNEL_SOURCE_OPTIONS = [
    {"id": "douyin", "label": "抖音", "icon_key": "douyin"},
    {"id": "wechat_official", "label": "公众号", "icon_key": "gongzhonghao"},
    {"id": "wechat_video", "label": "视频号", "icon_key": "shipinhao"},
    {"id": "wechat_private", "label": "微信私域", "icon_key": "wechat_private"},
    {"id": "xiaohongshu", "label": "小红书", "icon_key": "xiaohongshu"},
    {"id": "other", "label": "Other（其他/转介绍）", "icon_key": "other"},
]


@router.get("/channel-sources/config", response_model=ChannelSourceConfigResponse)
async def get_channel_sources_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取渠道来源配置（用于列表页/详情页下拉选项）。"""
    _ = current_user

    result = await db.execute(
        select(ChannelSourceOption)
        .where(ChannelSourceOption.is_active == 1)
        .order_by(ChannelSourceOption.sort_order, ChannelSourceOption.id)
    )
    options = result.scalars().all()

    if not options:
        # 兜底：未初始化数据库时，返回内置默认选项，避免前端不可用
        return {"options": CHANNEL_SOURCE_OPTIONS}

    payload = []
    for option in options:
        payload.append(
            {
                "id": option.id,
                "label": option.label,
                "icon_key": option.icon_key,
            }
        )
    return {"options": payload}


@router.put(
    "/records/{session_id}/channel-source",
    response_model=UpdateChannelSourceResponse,
)
async def update_record_channel_source(
    session_id: int,
    request: UpdateChannelSourceRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按 session_id 更新用户渠道来源标记（用户维度唯一）。"""
    _ = current_user

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = session.user_id
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(user_id=user_id)

    # 统一存储渠道来源为英文 id（兼容旧中文 label 输入/存量）
    normalized_channel_source = None
    if request.channel_source is not None and str(request.channel_source).strip():
        value = str(request.channel_source).strip()

        # 优先从 DB 配置读取映射
        result = await db.execute(select(ChannelSourceOption))
        options = result.scalars().all()
        if not options:
            # 兜底：使用内置常量映射
            options = [
                ChannelSourceOption(
                    id=o["id"], label=o["label"], icon_key=o.get("icon_key")
                )
                for o in CHANNEL_SOURCE_OPTIONS
            ]

        label_to_id = {o.label: o.id for o in options if getattr(o, "label", None)}
        id_set = {o.id for o in options if getattr(o, "id", None)}

        if value in id_set:
            normalized_channel_source = value
        elif value in label_to_id:
            normalized_channel_source = label_to_id[value]
        else:
            # 未知值：仍按原样保存（保持后端兼容“自由扩展”口径）
            normalized_channel_source = value

    profile.channel_source = normalized_channel_source
    profile.channel_ext_id = request.channel_ext_id
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return {
        "user_id": user_id,
        "channel_source": profile.channel_source,
        "channel_ext_id": profile.channel_ext_id,
    }

# --- 工具函数 ---

def format_rid(session_id: int, created_at: datetime) -> str:
    date_str = created_at.strftime("%Y%m%d")
    return f"R-{date_str}-{session_id:02d}"

def format_uid(user_id: int) -> str:
    return f"U-{user_id}"

def get_conversion_status(report: Report) -> str:
    """判断记录是否已转化。

    定义（与产品口径一致）：
    - 仅当用户点击“推荐产品”并触发后端生成/缓存推荐结果后，才算“已转化”。
    - 对应实现：Report.recommended_products 有值（非空）即视为已转化。
    """
    if not report:
        return "未转化"
    products = getattr(report, "recommended_products", None)
    if isinstance(products, list) and len(products) > 0:
        return "已转化"
    return "未转化"

def normalize_track_name(track_name: str) -> str:
    """
    标准化赛道名称，将各种变体映射到标准名称
    
    七大赛道标准名称：
    1. 消化赛道
    2. 骨骼与代谢赛道
    3. 神经赛道
    4. 免疫及血液赛道
    5. 内分泌赛道
    6. 皮肤赛道
    7. 心血管赛道
    """
    if not track_name or not isinstance(track_name, str):
        return "其他"
    
    track_name = track_name.strip()
    
    # 移除括号内的详细说明
    track_name = re.sub(r'\s*\([^)]*\)', '', track_name)  # 移除 (xxx)
    track_name = re.sub(r'\s*（[^）]*）', '', track_name)  # 移除 （xxx）
    track_name = re.sub(r'\s*\[.*?\]', '', track_name)  # 移除 [xxx]
    track_name = track_name.strip()
    
    # 移除编号前缀（如 "1. "、"4. "）
    track_name = re.sub(r'^\d+[\.、]\s*', '', track_name)
    
    # 标准化映射
    track_lower = track_name.lower()
    
    # 消化赛道
    if any(keyword in track_name for keyword in ['消化', '胃', '肠道', '肠', '便秘', '腹泻', '胀气', '口臭']):
        return "消化赛道"
    
    # 骨骼与代谢赛道
    if any(keyword in track_name for keyword in ['骨骼', '代谢', '关节', '腰酸', '背痛', '痛风', '肥胖', '体重', '乏力']):
        return "骨骼与代谢赛道"
    
    # 神经赛道
    if any(keyword in track_name for keyword in ['神经', '失眠', '睡眠', '多梦', '压力', '头痛', '记忆', '焦虑', '情绪', '抑郁']):
        return "神经赛道"
    
    # 免疫及血液赛道
    if any(keyword in track_name for keyword in ['免疫', '血液', '感冒', '过敏', '贫血', '虚弱', '术后', '恢复']):
        return "免疫及血液赛道"
    
    # 内分泌赛道
    if any(keyword in track_name for keyword in ['内分泌', '月经', '更年期', '甲状腺', '潮热']):
        return "内分泌赛道"
    
    # 皮肤赛道
    if any(keyword in track_name for keyword in ['皮肤', '痤疮', '色斑', '皱纹', '干燥', '出油', '抗衰', '抗衰老']):
        return "皮肤赛道"
    
    # 心血管赛道
    if any(keyword in track_name for keyword in ['心血管', '心慌', '胸闷', '血压', '血脂', '手脚冰凉']):
        return "心血管赛道"
    
    # 无/其他/未知
    if any(keyword in track_name for keyword in ['无', '其他', '未知', '话题无关', '不相关']):
        return "其他"
    
    # 如果完全匹配标准名称，直接返回
    standard_tracks = [
        "消化赛道", "骨骼与代谢赛道", "神经赛道", 
        "免疫及血液赛道", "内分泌赛道", "皮肤赛道", "心血管赛道"
    ]
    if track_name in standard_tracks:
        return track_name
    
    # 默认返回"其他"
    return "其他"

def get_track_color(track_name: str) -> str:
    """
    根据赛道名称返回对应的颜色类名
    颜色顺序：蓝色、绿色、橙色、灰色、青色、红色、深色
    """
    color_map = {
        "神经赛道": "bg-primary",  # 蓝色 - 睡眠与神经
        "消化赛道": "bg-success",  # 绿色 - 肠道与代谢
        "皮肤赛道": "bg-warning",  # 橙色 - 皮肤抗衰
        "骨骼与代谢赛道": "bg-info",  # 青色
        "免疫及血液赛道": "bg-danger",  # 红色
        "内分泌赛道": "bg-secondary",  # 灰色
        "心血管赛道": "bg-dark",  # 深色
        "其他": "bg-secondary"  # 灰色
    }
    return color_map.get(track_name, "bg-secondary")

# --- 时间工具 ---

def format_cn_date(dt: datetime) -> str:
    """将数据库时间转换为中国时区(Asia/Shanghai)的日期字符串(YYYY-MM-DD)。

    Notes:
        - 当前项目多数表的 created_at/updated_at 使用 SQLite 的 CURRENT_TIMESTAMP，
          通常为 UTC 且为“无 tzinfo 的 naive datetime”。
        - 为避免跨日偏差，这里统一按“naive=UTC”解释，再转换到 Asia/Shanghai。
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    cn_dt = dt.astimezone(ZoneInfo("Asia/Shanghai"))
    return cn_dt.strftime("%Y-%m-%d")

def format_cn_datetime(dt: datetime) -> str:
    """将数据库时间转换为中国时区(Asia/Shanghai)的时间字符串(YYYY-MM-DD HH:MM:SS)。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    cn_dt = dt.astimezone(ZoneInfo("Asia/Shanghai"))
    return cn_dt.strftime("%Y-%m-%d %H:%M:%S")


# --- 看板接口 ---

@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    dashboard_cache = Depends(get_dashboard_cache_service),
):
    """获取核心指标数据 (部分 Mock)"""
    _ = current_user
    return await dashboard_cache.get_metrics(db=db)

@router.get("/dashboard/funnel", response_model=DashboardFunnelResponse)
async def get_dashboard_funnel(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    dashboard_cache = Depends(get_dashboard_cache_service),
):
    """获取漏斗数据"""
    _ = current_user
    return await dashboard_cache.get_funnel(db=db)

@router.get("/dashboard/distribution", response_model=DashboardDistributionResponse)
async def get_dashboard_distribution(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    dashboard_cache = Depends(get_dashboard_cache_service),
):
    """
    获取赛道分布数据
    
    统计逻辑：
    1. 从 Session.meta_data 中读取 track 字段
    2. 使用 normalize_track_name() 标准化赛道名称
    3. 统计每个标准赛道的会话数量
    4. 计算百分比并返回，按数量降序排列
    """
    distribution = await dashboard_cache.get_track_distribution(
        db=db,
        normalize_track_name=normalize_track_name,
        get_track_color=get_track_color,
    )
    return {"distribution": distribution}


# --- 记录列表接口 ---

@router.get("/records/list", response_model=RecordListResponse)
async def get_records_list(
    current_user = Depends(get_current_user),
    page: int = 1,
    page_size: int = 10,
    track: str = None,
    status: str = None,
    search: str = None,
    report_date: str = None,
    channel_source: str = None,
    db: AsyncSession = Depends(get_db)
):
    """分页获取评估记录列表"""
    query = (
        select(Session, Report, User, UserProfile)
        .join(User, Session.user_id == User.id)
        .outerjoin(Report, Session.id == Report.session_id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
    )

    # SQL 层过滤：按列表展示日期过滤（Session.created_at 的中国自然日）
    if report_date is not None and str(report_date).strip():
        report_date_str = str(report_date).strip()
        try:
            report_day = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="report_date 格式错误，必须为 YYYY-MM-DD",
            ) from exc

        # 按中国自然日过滤：将 Asia/Shanghai 的日界线转换为 UTC 再做 DB compare
        cn_tz = ZoneInfo("Asia/Shanghai")
        start_cn = datetime.combine(report_day, datetime.min.time(), tzinfo=cn_tz)
        end_cn = start_cn + timedelta(days=1)
        start_dt = start_cn.astimezone(timezone.utc).replace(tzinfo=None)
        end_dt = end_cn.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.where(
            Session.created_at.isnot(None),
            Session.created_at >= start_dt,
            Session.created_at < end_dt,
        )

    # SQL 层过滤：按渠道来源过滤（UserProfile.channel_source）
    # 兼容：历史数据可能存中文 label（如“抖音”），新口径存英文 id（如“douyin”）
    if channel_source is not None and str(channel_source).strip():
        cs_input = str(channel_source).strip()

        result = await db.execute(select(ChannelSourceOption))
        options = result.scalars().all()
        if not options:
            # 兜底：使用内置常量映射
            options = [
                ChannelSourceOption(
                    id=o["id"], label=o["label"], icon_key=o.get("icon_key")
                )
                for o in CHANNEL_SOURCE_OPTIONS
            ]

        id_to_label = {o.id: o.label for o in options if getattr(o, "id", None)}
        label_to_id = {o.label: o.id for o in options if getattr(o, "label", None)}

        values = {cs_input}
        if cs_input in id_to_label:
            values.add(id_to_label[cs_input])
        if cs_input in label_to_id:
            values.add(label_to_id[cs_input])

        query = query.where(UserProfile.channel_source.in_(list(values)))
    
    # 排序：按会话创建时间（与 time 字段口径一致）
    query = query.order_by(desc(Session.created_at))
    
    # 简单的内存过滤 (复杂过滤建议在 DB 层，但 JSON 字段过滤在 SQLite/PG 间有差异)
    # 这里先取出分页的一批，注意：这种方式在数据量大时有性能问题，
    # 但由于 Track 在 JSON 中，且 Status 是 Mock 的，只能这样处理或 Mock DB字段。
    # 修正：为了演示，我们先只做 DB 层的分页，Filter 逻辑简单处理
    
    # 计算 offset
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    # 获取总数（应用 report_date / channel_source 过滤条件）
    count_query = (
        select(func.count(func.distinct(Session.id)))
        .select_from(Session)
        .join(User, Session.user_id == User.id)
        .outerjoin(Report, Session.id == Report.session_id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
    )
    if report_date is not None and str(report_date).strip():
        report_date_str = str(report_date).strip()
        try:
            report_day = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="report_date 格式错误，必须为 YYYY-MM-DD",
            ) from exc
        cn_tz = ZoneInfo("Asia/Shanghai")
        start_cn = datetime.combine(report_day, datetime.min.time(), tzinfo=cn_tz)
        end_cn = start_cn + timedelta(days=1)
        start_dt = start_cn.astimezone(timezone.utc).replace(tzinfo=None)
        end_dt = end_cn.astimezone(timezone.utc).replace(tzinfo=None)
        count_query = count_query.where(
            Session.created_at.isnot(None),
            Session.created_at >= start_dt,
            Session.created_at < end_dt,
        )
    if channel_source is not None and str(channel_source).strip():
        cs_input = str(channel_source).strip()

        result = await db.execute(select(ChannelSourceOption))
        options = result.scalars().all()
        if not options:
            options = [
                ChannelSourceOption(
                    id=o["id"], label=o["label"], icon_key=o.get("icon_key")
                )
                for o in CHANNEL_SOURCE_OPTIONS
            ]

        id_to_label = {o.id: o.label for o in options if getattr(o, "id", None)}
        label_to_id = {o.label: o.id for o in options if getattr(o, "label", None)}

        values = {cs_input}
        if cs_input in id_to_label:
            values.add(id_to_label[cs_input])
        if cs_input in label_to_id:
            values.add(label_to_id[cs_input])

        count_query = count_query.where(UserProfile.channel_source.in_(list(values)))
    total_result = await db.scalar(count_query)
    
    records = []
    for session, report, user, user_profile in rows:
        # 解析 Track（支持多赛道）
        current_tracks = []
        if session.meta_data and isinstance(session.meta_data, dict):
            tracks = session.meta_data.get("track", [])
            if isinstance(tracks, str):
                current_tracks = [tracks]  # 兼容旧数据
            elif isinstance(tracks, list):
                current_tracks = tracks
        current_track = "、".join(current_tracks) if current_tracks else "未知赛道"
            
        # 转化状态：仅当用户点击“推荐产品”触发缓存后才算已转化
        current_status = get_conversion_status(report)
        
        # 风险等级
        risk = "未评估"
        health_score = None
        if report:
            risk = report.risk_level or "未评估"
            # 简单的风险转换逻辑，保证前端样式
            if "高" in risk: risk = "高"
            elif "中" in risk: risk = "中"
            elif "低" in risk: risk = "低"

            # 健康分：优先 Report.score，缺失时从 baichuan_json.score 取
            health_score = report.score
            if health_score is None and report.content and isinstance(report.content, dict):
                try:
                    baichuan_json = report.content.get("baichuan_json") or {}
                    if isinstance(baichuan_json, dict):
                        raw_score = baichuan_json.get("score")
                        if raw_score is not None:
                            health_score = int(raw_score)
                except Exception:
                    health_score = report.score
        
        # 过滤逻辑 (内存中补充过滤，实际生产应在 SQL 中)
        # 支持多赛道过滤：如果传入的track在current_tracks中，则匹配
        if track:
            if isinstance(current_tracks, str):
                current_tracks = [current_tracks]
            if track not in current_tracks:
                continue
        if status and status != current_status:
            continue
        # 搜索过滤：支持在用户ID、记录ID等字段中搜索
        if search:
            search_lower = search.lower()
            uid_match = format_uid(user.id).lower().find(search_lower) >= 0
            rid_match = format_rid(session.id, session.created_at).lower().find(search_lower) >= 0
            track_match = current_track.lower().find(search_lower) >= 0
            if not (uid_match or rid_match or track_match):
                continue
            
        # 列表展示时间：统一使用会话创建时间（Session.created_at）
        display_time = session.created_at
            
        records.append(RecordListItem(
            rid=format_rid(session.id, session.created_at),
            uid=format_uid(user.id),
            session_id=session.id,
            user_id=user.id,
            track=current_track,
            risk=risk,
            health_score=health_score,
            time=format_cn_date(display_time),
            report_time=format_cn_datetime(report.created_at) if report and getattr(report, "created_at", None) is not None else None,
            status=current_status,
            channel_source=getattr(user_profile, "channel_source", None),
            channel_ext_id=getattr(user_profile, "channel_ext_id", None),
        ))
        
    return {
        "total": total_result or 0,
        "records": records
    }

@router.get("/records/{session_id}", response_model=RecordDetailResponse)
async def get_record_detail(
    session_id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单条记录详情"""
    # 查询 Session, Report, User
    result = await db.execute(
        select(Session, Report, User, UserProfile)
        .join(User, Session.user_id == User.id)
        .outerjoin(Report, Session.id == Report.session_id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .where(Session.id == session_id)
    )
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session, report, user, user_profile = row
    
    # 查询消息构建 QnA
    msgs_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = msgs_result.scalars().all()

    # 完整问卷/对话：按时间顺序返回（前端可直接渲染）
    message_items = []
    for msg in messages:
        if msg.role not in ("user", "assistant"):
            continue
        if msg.content is None:
            continue
        message_items.append(
            RecordMessageItem(
                role=str(msg.role),
                content=str(msg.content),
                created_at=msg.created_at,
            )
        )
    
    qna_list = []
    # 简单策略：提取所有 role=user 的消息作为 A，它前面的一条作为 Q
    for i, msg in enumerate(messages):
        if msg.role == "user":
            answer = msg.content
            question = "AI 提问"
            if i > 0 and messages[i-1].role == "assistant":
                # 截取前 15 个字符作为问题摘要
                prev_content = messages[i-1].content
                # 清理一下内容，去掉"【给用户的回复】"等
                if "【给用户的回复】" in prev_content:
                    prev_content = prev_content.split("【给用户的回复】")[-1].strip()
                question = prev_content[:10] + "..."
            
            qna_list.append(f"Q:{question} A:{answer}")
            
    qna_str = "; ".join(qna_list)
    
    # 提取报告 HTML
    report_html = "<div>暂无报告数据</div>"
    risk = "未评估"
    score = None
    
    if report and report.content and isinstance(report.content, dict):
        report_html = report.content.get("html", "")
        risk = report.risk_level or "未评估"
        if "高" in risk: risk = "高"
        elif "中" in risk: risk = "中"
        elif "低" in risk: risk = "低"
        # 评分优先使用 Report.score，缺失时尝试从 baichuan_json 取
        score = report.score
        try:
            baichuan_json = (report.content or {}).get("baichuan_json") or {}
            if score is None and isinstance(baichuan_json, dict):
                raw_score = baichuan_json.get("score")
                if raw_score is not None:
                    score = int(raw_score)
        except Exception:
            score = report.score

    # 兼容 track 字段（支持多赛道）
    current_tracks = []
    if session.meta_data and isinstance(session.meta_data, dict):
        tracks = session.meta_data.get("track", [])
        if isinstance(tracks, str):
            current_tracks = [tracks]  # 兼容旧数据
        elif isinstance(tracks, list):
            current_tracks = tracks
    current_track = "、".join(current_tracks) if current_tracks else "未知赛道"

    # 兼容：从 meta_data 中提取年龄/性别（若存在）
    age = None
    gender = None
    if session.meta_data and isinstance(session.meta_data, dict):
        try:
            raw_age = session.meta_data.get("age") or session.meta_data.get("年龄")
            if raw_age is not None and str(raw_age).strip():
                age = int(str(raw_age).strip())
        except Exception:
            age = None
        raw_gender = session.meta_data.get("gender") or session.meta_data.get("sex") or session.meta_data.get("性别")
        if raw_gender:
            raw_gender = str(raw_gender)
            if "女" in raw_gender:
                gender = "女"
            elif "男" in raw_gender:
                gender = "男"

    # 尝试从用户自由文本里推断（如果 meta_data 没有提供）
    if age is None or gender is None:
        combined_user_text = "；".join(
            [(m.content or "").strip() for m in messages if m.role == "user"]
        )
        import re
        if age is None:
            match = re.search(r"(\\d{1,3})\\s*岁", combined_user_text)
            if match:
                try:
                    age = int(match.group(1))
                except Exception:
                    age = None
        if gender is None:
            if "女" in combined_user_text and "男性" not in combined_user_text:
                gender = "女"
            elif "男" in combined_user_text and "女性" not in combined_user_text:
                gender = "男"

    return RecordDetailResponse(
        rid=format_rid(session.id, session.created_at),
        uid=format_uid(user.id),
        track=current_track,
        risk=risk,
        status=get_conversion_status(report),
        qna=qna_str,
        messages=message_items,
        report_html=report_html,
        created_at=session.created_at,
        age=age,
        gender=gender,
        score=score,
        channel_source=getattr(user_profile, "channel_source", None),
        channel_ext_id=getattr(user_profile, "channel_ext_id", None),
    )


@router.get("/sales-script/config", response_model=SalesScriptConfigResponse)
async def get_sales_script_config(
    current_user=Depends(get_current_user),
):
    """获取销售助手配置面板选项（目前仅 Tone）。"""
    _ = current_user  # 保留鉴权
    return {
        "tones": [
            {"id": "expert", "label": "👩‍⚕️ 专业专家（建议首选）", "is_default": True},
            {"id": "friend", "label": "👭 贴心闺蜜", "is_default": False},
        ]
    }


@router.post(
    "/records/{session_id}/sales-script/generate",
    response_model=SalesScriptGenerateResponse,
)
async def generate_sales_script(
    session_id: int,
    request: SalesScriptGenerateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成右侧 AI 销售助手三段式话术（DeepSeek 高思考模型）。"""
    _ = current_user  # 保留鉴权
    from src.services.sales_script_service import sales_script_service

    try:
        payload = await sales_script_service.generate_sales_script(
            db,
            session_id=session_id,
            tone=request.tone,
            channel=request.channel,
            channel_source=request.channel_source,
            recommendation_rule_id=request.recommendation_rule_id,
        )
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("生成销售话术失败 session_id=%s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="生成销售话术失败")


@router.get(
    "/records/{session_id}/sales-script",
    response_model=SalesScriptGenerateResponse,
)
async def get_saved_sales_script(
    session_id: int,
    tone: str = "expert",
    channel: str = "wechat_private",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取销售助手话术（仅读取：有则返回，无则返回空结构；不调用大模型）。"""
    _ = current_user
    from src.services.sales_script_service import sales_script_service

    payload = await sales_script_service.build_saved_sales_script_response(
        db,
        session_id=session_id,
        tone_default="expert",
        channel_default=channel,
    )
    # 未保存时固定 expert（即便 query 传 friend）
    if not payload.get("is_saved"):
        payload["tone"] = "expert"
    return payload


@router.put(
    "/records/{session_id}/sales-script",
    response_model=SalesScriptGenerateResponse,
)
async def save_sales_script(
    session_id: int,
    request: SalesScriptSaveRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存编辑后的三段式话术，并返回回显结构（含高亮）。"""
    _ = current_user
    from src.services.sales_script_service import ReportNotFoundError, sales_script_service

    try:
        saved = await sales_script_service.save_sales_script(
            db,
            session_id=session_id,
            tone=request.tone,
            channel=request.channel or "wechat_private",
            channel_source=request.channel_source,
            step1_text=request.step1_text,
            step2_text=request.step2_text,
            step3_text=request.step3_text,
            search_keyword=request.search_keyword,
            core_ingredient_name=request.core_ingredient_name,
        )
    except ReportNotFoundError as exc:
        # 业务可预期错误：尚未生成报告时不允许保存“按报告绑定”的话术
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.exception("保存销售话术失败 session_id=%s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="保存销售话术失败")

    # 复用 get_saved_sales_script 的回显逻辑（确保高亮一致）
    payload = await get_saved_sales_script(
        session_id=session_id,
        tone=saved.tone,
        channel=saved.channel,
        current_user=current_user,
        db=db,
    )
    payload["is_saved"] = True
    return payload

