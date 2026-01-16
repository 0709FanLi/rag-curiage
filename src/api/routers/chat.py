from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, Dict, List
from src.models.database import get_db
from src.models.tables import User, Session as DBSession, Message
from src.api.dependencies import get_current_user
from src.config.settings import settings
from src.services.business_service import business_service
from src.services.qwen_vl_service import qwen_vl_service
from src.services.baichuan_service import baichuan_service
from src.services.oss_service import OSSService
from src.services.session_attachment_service import OCR_SOURCE_URLS_KEY, set_attached_file_urls
import logging
from urllib.parse import urlparse
import httpx
from pypdf import PdfReader
import pypdfium2 as pdfium
import io
import uuid

logger = logging.getLogger("healthy_rag")
router = APIRouter()

class MessageItem(BaseModel):
    role: str
    content: str

class StartSessionResponse(BaseModel):
    session_id: int
    messages: List[MessageItem]

class ChatRequest(BaseModel):
    session_id: int
    content: str

class ChatResponse(BaseModel):
    messages: Optional[List[str]] = None  # 多条消息（新格式）
    response: Optional[str] = None  # 单条消息（兼容旧格式）
    action: str  # 'chat' or 'report'
    report_data: Optional[Dict] = None

class SessionHistoryResponse(BaseModel):
    session_id: Optional[int] = None
    messages: List[MessageItem] = []
    ocr_text: Optional[str] = None
    ocr_tags: Optional[List[str]] = None
    uploaded_file_url: Optional[str] = None
    track: Optional[List[str]] = None  # 赛道信息（1-2个赛道）

class SessionListItem(BaseModel):
    """会话列表项（用于“我的对话”列表）。"""

    session_id: int
    preview: str
    updated_at: str


class SessionListResponse(BaseModel):
    """会话列表响应。"""

    sessions: List[SessionListItem]

@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 创建新会话
    session = await business_service.create_session(db, current_user.id)
    
    # 初始欢迎语（分成两条独立消息）
    # 第一条消息：问候语
    greeting_msg = "您好！我是您的 AI 健康管家。"
    msg1 = Message(session_id=session.id, role="assistant", content=greeting_msg)
    db.add(msg1)
    
    # 第二条消息：指引语
    instruction_msg = "为了提供精准的评估，我们需要为您进行定制化的对话采集。请描述您的年龄、性别，上传体检报告或分析报告（可点击上传按钮上传，非必须），以及最近最困扰您的问题。"
    msg2 = Message(session_id=session.id, role="assistant", content=instruction_msg)
    db.add(msg2)
    
    await db.commit()
    
    # 返回两条消息
    return {
        "session_id": session.id,
        "messages": [
            {"role": "assistant", "content": greeting_msg},
            {"role": "assistant", "content": instruction_msg}
        ]
    }

@router.get("/active", response_model=SessionHistoryResponse)
async def get_active_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的活跃会话和历史消息"""
    try:
        # 查找最新的活跃会话
        result = await db.execute(
            select(DBSession)
            .where(DBSession.user_id == current_user.id)
            .where(DBSession.status == "active")
            .order_by(desc(DBSession.created_at))
        )
        session = result.scalars().first()  # 使用 first() 获取第一个结果
        logger.info("------------session--------------: %s", session)
        if not session:
            # 没有活跃会话时返回空数据，前端会调用/start创建新会话
            return {
                "session_id": None,
                "messages": []
            }
        
        # 获取该会话的所有消息
        messages_result = await db.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.created_at)
        )
        messages = messages_result.scalars().all()
        
        return {
            "session_id": session.id,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in get_active_session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的会话列表（按更新时间倒序）。"""
    # 查 session（更新时间倒序）
    result = await db.execute(
        select(DBSession)
        .where(DBSession.user_id == current_user.id)
        .order_by(desc(DBSession.updated_at))
        .limit(100)
    )
    sessions = result.scalars().all()

    items: List[Dict[str, str | int]] = []
    for s in sessions:
        # 取该会话第一条 user 消息作为预览
        msg_result = await db.execute(
            select(Message)
            .where(Message.session_id == s.id)
            .where(Message.role == "user")
            .order_by(Message.created_at)
            .limit(1)
        )
        first_user = msg_result.scalar_one_or_none()
        # 仅 AI 欢迎语/无用户输入的“空会话”不应出现在会话列表（对齐 PC 行为）
        if not first_user:
            continue
        preview = first_user.content
        if len(preview) > 50:
            preview = preview[:50] + "..."
        items.append(
            {
                "session_id": s.id,
                "preview": preview,
                "updated_at": (s.updated_at.isoformat() if s.updated_at else ""),
            }
        )

    return {"sessions": items}

@router.get("/session/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定会话的历史消息和详细信息"""
    # 验证 session 归属
    result = await db.execute(
        select(DBSession).where(DBSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取该会话的所有消息
    messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()

    # 仅有 AI 欢迎语、没有用户输入的会话：不作为“历史对话”返回（对齐 PC 行为）
    if not any(m.role == "user" for m in messages):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取赛道信息（兼容旧数据）
    tracks = []
    if session.meta_data and isinstance(session.meta_data, dict):
        track_data = session.meta_data.get("track", [])
        if isinstance(track_data, str):
            tracks = [track_data]  # 兼容旧数据
        elif isinstance(track_data, list):
            tracks = track_data
    
    return {
        "session_id": session.id,
        "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
        "ocr_text": session.ocr_text,
        "ocr_tags": session.ocr_tags,
        "uploaded_file_url": session.uploaded_file_url,
        "track": tracks  # 返回赛道数组
    }

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 验证 session 属于当前用户
    session = await business_service.get_session(db, request.session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
        
    # 处理消息
    result = await business_service.process_chat(db, request.session_id, request.content)
    
    return result


class UploadReportRequest(BaseModel):
    session_id: int
    file_urls: List[str]  # 改为支持多个图片URL
    force_reparse: bool = False  # 强制失效 OCR 缓存并重新解析


class UploadReportResponse(BaseModel):
    success: bool
    message: str
    # 兼容旧前端：保留字段，但不再在上传阶段解析
    ocr_text: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/upload-report", response_model=UploadReportResponse)
async def upload_and_parse_report(
    request: UploadReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    绑定会话附件（图片/PDF），不做预解析。
    
    说明：
    - 前端先调用 `/upload/file` 完成文件上传拿到 `file_url`
    - 再调用本接口把 `file_urls` 绑定到 session
    - OCR 解析会延迟到“生成报告”时执行（见 report 生成后台任务）
    
    Args:
        request: 包含 session_id 和 file_urls（多个图片URL）
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        绑定结果（不返回 OCR/标签）
    """
    try:
        # 1. 验证 session
        session = await business_service.get_session(db, request.session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )

        urls = await set_attached_file_urls(db, session, request.file_urls or [])

        # 强制重新解析：即使 urls 列表没有变化，也要清空 OCR 并移除缓存标记
        # 场景：用户在 OSS 覆盖同一个 URL 的文件内容（URL 不变但内容变了）
        if request.force_reparse:
            try:
                meta = session.meta_data or {}
                if isinstance(meta, dict):
                    meta.pop(OCR_SOURCE_URLS_KEY, None)
                session.meta_data = meta
                session.ocr_text = None
                session.ocr_tags = None
                db.add(session)
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "force_reparse failed (non-blocking) session=%s err=%s",
                    request.session_id,
                    exc,
                )
        logger.info(
            "用户 %s 绑定会话附件 session=%s count=%s",
            current_user.username,
            request.session_id,
            len(urls),
        )
        return {
            "success": True,
            "message": f"已绑定 {len(urls)} 个附件",
            "ocr_text": None,
            "tags": None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"报告解析失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"报告解析失败: {str(e)}"
        )
