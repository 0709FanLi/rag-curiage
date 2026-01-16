from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, update
from sqlalchemy.exc import OperationalError
from src.models.database import get_db, AsyncSessionLocal
from src.models.tables import Report, Session, User
from src.api.dependencies import get_current_user
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import asyncio
import jwt
from jwt import PyJWTError

from src.config.settings import settings

# 生产环境：用于剥离 report.content.html 里可能残留的前置 JSON
from src.services.report_html_sanitizer import find_html_start_index, strip_leading_json

# 配置 logger
logger = logging.getLogger(__name__)

router = APIRouter()

class ReportResponse(BaseModel):
    id: int
    session_id: int  # 添加session_id字段
    score: int
    risk_level: str
    content: Dict[str, Any]
    baichuan_suggestions: Optional[str] = None  # 百川模型返回的健康建议
    created_at: datetime

class ReportListItem(BaseModel):
    session_id: int
    report_id: int
    score: int
    risk_level: str
    created_at: datetime
    preview: str  # 会话预览文字

class ReportListResponse(BaseModel):
    reports: List[ReportListItem]

async def run_bg_report_generation(session_id: int):
    """后台任务：生成报告。

    Notes:
        - OCR 解析属于可选增强能力：失败时应降级为“仅基于问卷/对话生成报告”，避免整个报告卡死。
        - 若后台任务最终失败，必须将 Report.content 标记为 error，避免前端无限轮询。
    """
    logger.info("Starting background report generation for session %s", session_id)
    async with AsyncSessionLocal() as db:
        from src.services.business_service import business_service
        from src.services.report_parse_service import report_parse_service
        try:
            # 延迟解析：仅在生成报告时解析附件，上传阶段不做预解析
            # OCR 解析失败时降级继续（例如第三方OCR额度耗尽/网络波动）
            try:
                await report_parse_service.ensure_session_ocr_text(db, session_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OCR parsing failed, fallback to questionnaire-only report. session=%s err=%s",
                    session_id,
                    exc,
                )

            await business_service.generate_report_content(db, session_id)
            logger.info("Background report generation completed for session %s", session_id)
        except Exception as exc:  # noqa: BLE001
            # 关键：必须落库错误状态，避免前端无限轮询
            try:
                report_result = await db.execute(
                    select(Report).where(Report.session_id == session_id)
                )
                report = report_result.scalar_one_or_none()
                if report:
                    report.content = {
                        "status": "error",
                        "error": str(exc),
                        "html": "",
                    }
                    db.add(report)

                session_result = await db.execute(
                    select(Session).where(Session.id == session_id)
                )
                session = session_result.scalar_one_or_none()
                if session and session.status == "generating_report":
                    session.status = "active"
                    db.add(session)

                await db.commit()
            except Exception as persist_exc:  # noqa: BLE001
                await db.rollback()
                logger.exception(
                    "Failed to persist report error state session=%s: %s",
                    session_id,
                    persist_exc,
                )

            logger.error(
                "Background report generation failed for session %s: %s",
                session_id,
                exc,
            )

async def cache_report_recommendations(
    report_id: int,
    recommendations: List[Dict[str, Any]],
    max_attempts: int = 5,
) -> None:
    """后台任务：尽力缓存推荐结果到报告中（避免因SQLite写锁导致接口失败）。

    Args:
        report_id: 报告ID
        recommendations: 推荐结果列表（可JSON序列化）
        max_attempts: 最大重试次数
    """
    backoff_seconds = 0.2
    async with AsyncSessionLocal() as db:
        for attempt in range(1, max_attempts + 1):
            try:
                stmt = (
                    update(Report)
                    .where(Report.id == report_id)
                    .where(Report.recommended_products.is_(None))
                    .values(recommended_products=recommendations)
                )
                result = await db.execute(stmt)
                await db.commit()

                if result.rowcount:
                    logger.info(
                        "已缓存推荐结果到报告 report_id=%s (count=%s)",
                        report_id,
                        len(recommendations),
                    )
                else:
                    logger.info(
                        "报告 report_id=%s 已存在缓存推荐结果，跳过写入",
                        report_id,
                    )
                return
            except OperationalError as exc:
                await db.rollback()
                message = str(exc).lower()
                if "database is locked" not in message:
                    logger.exception(
                        "缓存推荐结果失败（非锁错误） report_id=%s: %s",
                        report_id,
                        exc,
                    )
                    return

                if attempt >= max_attempts:
                    logger.warning(
                        "缓存推荐结果多次遇到SQLite写锁，放弃写入 report_id=%s",
                        report_id,
                    )
                    return

                logger.warning(
                    "缓存推荐结果遇到SQLite写锁，重试 %s/%s report_id=%s",
                    attempt,
                    max_attempts,
                    report_id,
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds *= 2
            except Exception as exc:
                await db.rollback()
                logger.exception(
                    "缓存推荐结果异常 report_id=%s: %s",
                    report_id,
                    exc,
                )
                return

# ⚠️ 重要：具体路由必须在参数路由之前定义
@router.get("/list", response_model=ReportListResponse)
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的所有报告列表"""
    from src.models.tables import Message
    
    # 查询用户所有的 session（有报告的）
    result = await db.execute(
        select(Session, Report)
        .join(Report, Session.id == Report.session_id)
        .where(Session.user_id == current_user.id)
        .order_by(desc(Report.created_at))
    )
    session_reports = result.all()
    
    reports_list = []
    for session, report in session_reports:
        # 获取该 session 的第一条用户消息作为预览
        msg_result = await db.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .where(Message.role == "user")
            .order_by(Message.created_at)
            .limit(1)
        )
        first_msg = msg_result.scalar_one_or_none()
        preview = first_msg.content[:50] + "..." if first_msg and len(first_msg.content) > 50 else (first_msg.content if first_msg else "无预览")
        
        reports_list.append({
            "session_id": session.id,
            "report_id": report.id,
            "score": report.score,
            "risk_level": report.risk_level,
            "created_at": report.created_at,
            "preview": preview
        })
    
    return {"reports": reports_list}

@router.get("/{session_id}", response_model=ReportResponse)
async def get_report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 验证 session 归属
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 获取报告
    report_result = await db.execute(select(Report).where(Report.session_id == session_id))
    report = report_result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # 兼容：历史数据/线上异常时，content.html 可能被写入“JSON + HTML”
    # 这里做一次只读修复，避免前端把 JSON 当作 HTML 渲染。
    try:
        content = report.content or {}
        if isinstance(content, dict) and content.get("status") == "completed":
            raw_html = content.get("html") or ""
            if isinstance(raw_html, str) and raw_html.lstrip().startswith(("{", "[")):
                # 先按 HTML 起点切分（若存在）
                idx = find_html_start_index(raw_html)
                if idx != -1:
                    content = {**content, "html": raw_html[idx:].lstrip()}
                else:
                    sanitized, _ = strip_leading_json(raw_html)
                    # 即使 sanitized 为空，也不要把 JSON 透传给前端渲染
                    content = {**content, "html": sanitized}
    except Exception:
        # 只读兜底，不影响接口返回
        content = report.content

    return {
        "id": report.id,
        "session_id": report.session_id,
        "score": report.score,
        "risk_level": report.risk_level,
        "content": content,
        "baichuan_suggestions": report.baichuan_suggestions,
        "created_at": report.created_at
    }


async def _get_user_from_request_token(
    *,
    http_request: Request,
    db: AsyncSession,
) -> User:
    """在 webview 场景下允许通过 query token 访问（webview 无法稳定携带 Authorization header）。"""
    token = http_request.query_params.get("token")
    if not token:
        auth = http_request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as exc:
        logger.exception("解析 webview token 失败（非 JWT 错误）: %s", exc)
        raise HTTPException(status_code=500, detail="Token decode error")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.get("/{session_id}/html", response_class=HTMLResponse)
async def get_report_html(
    session_id: int,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """返回可直接渲染的 HTML（给移动端 web-view 使用）。"""
    current_user = await _get_user_from_request_token(http_request=http_request, db=db)

    # 验证 session 归属
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    report_result = await db.execute(select(Report).where(Report.session_id == session_id))
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    content = report.content or {}
    status_value = content.get("status") if isinstance(content, dict) else None
    html = ""
    if isinstance(content, dict):
        html = (content.get("html") or "") if isinstance(content.get("html"), str) else ""

    if status_value in ("generating", "error") or not html.strip():
        # 内置轻量轮询：3s 自动刷新一次（直到 completed）
        hint = "报告生成中，请稍候..." if status_value == "generating" else "报告生成失败，请稍后刷新重试"
        safe_title = "健康报告"
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 16px; }}
    .card {{ background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 16px; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
  <div class="card">
    <div>{hint}</div>
    <div class="muted" style="margin-top:8px;">页面将自动刷新</div>
  </div>
  <script>
    setTimeout(function() {{ location.reload(); }}, 3000);
  </script>
</body>
</html>"""

    return HTMLResponse(content=html, status_code=200)

@router.post("/{session_id}/generate")
async def generate_report(
    session_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """触发报告生成（如果尚未生成）"""
    
    # 验证 session 归属
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取报告
    report_result = await db.execute(select(Report).where(Report.session_id == session_id))
    report = report_result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # 检查报告状态
    status = (report.content or {}).get("status")
    raw_html = (report.content or {}).get("html") if isinstance(report.content, dict) else ""

    should_regenerate = False
    if status == "completed" and isinstance(raw_html, str) and (
        not raw_html.strip() or raw_html.lstrip().startswith(("{", "["))
    ):
        # 线上异常：html 被写入了 JSON 开头，允许重新生成一次
        should_regenerate = True

    if status == "generating" or should_regenerate:
        if should_regenerate:
            # 将状态回滚到 generating，触发后台重跑（BusinessService 只对 generating 生效）
            report.content = {**(report.content or {}), "status": "generating", "html": ""}
            db.add(report)
            await db.commit()
        # 使用后台任务执行生成逻辑，避免前端超时
        background_tasks.add_task(run_bg_report_generation, session_id)
    
    return {
        "id": report.id,
        "session_id": report.session_id,
        "score": report.score,
        "risk_level": report.risk_level,
        "content": report.content,
        "baichuan_suggestions": report.baichuan_suggestions,
        "created_at": report.created_at
    }


# ========== 产品推荐相关 ==========

class ProductRecommendationItem(BaseModel):
    rule_id: str
    track: str
    risk_level: str
    matched_tags: List[str]
    product_info: Dict[str, Any]


class ProductRecommendationsResponse(BaseModel):
    success: bool
    recommendations: List[ProductRecommendationItem]
    total: int


@router.get("/{session_id}/recommendations", response_model=ProductRecommendationsResponse)
async def get_product_recommendations(
    session_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取产品推荐
    
    根据 session 的赛道和 OCR 提取的标签，推荐相关产品
    
    Args:
        session_id: 会话ID
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        推荐产品列表
    """
    try:
        # 1. 验证 session 属于当前用户
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="Session not found or access denied"
            )
        
        # 2. 检查是否有报告
        report_result = await db.execute(
            select(Report).where(Report.session_id == session_id)
        )
        report = report_result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(
                status_code=404,
                detail="Report not found. Please generate report first."
            )
        
        # 3. 如果报告中已有推荐产品，直接返回
        if report.recommended_products:
            logger.info(f"返回已缓存的推荐产品: session {session_id}")
            return {
                "success": True,
                "recommendations": report.recommended_products,
                "total": len(report.recommended_products)
            }
        
        # 4. 调用推荐服务生成推荐
        from src.services.product_recommendation_service import product_recommendation_service
        
        logger.info(f"为 session {session_id} 生成产品推荐...")
        recommendations = await product_recommendation_service.get_recommended_products_by_session(
            db, session_id
        )

        # 5. 异步缓存推荐结果（避免SQLite写锁导致接口失败）
        background_tasks.add_task(
            cache_report_recommendations,
            report.id,
            recommendations,
        )

        logger.info(
            "产品推荐完成（返回结果，后台缓存）session=%s count=%s",
            session_id,
            len(recommendations),
        )
        
        return {
            "success": True,
            "recommendations": recommendations,
            "total": len(recommendations)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取产品推荐失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"获取产品推荐失败: {str(e)}"
        )
