import re
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.models.tables import Session, Message, Report
from src.services.llm_service import llm_service
from src.services.baichuan_service import baichuan_service
from typing import Optional

from src.services.prompts import PHASE_0_CHECK, REPORT_GENERATION
from src.services.report_prompt_loader import load_report_prompts, load_report_html_template
from src.services.report_html_sanitizer import find_html_start_index, strip_leading_json


def _strip_code_fences(text: str) -> str:
    return re.sub(r"^```(?:json|html)?\s*|\s*```$", "", (text or "").strip(), flags=re.IGNORECASE | re.MULTILINE).strip()


def _extract_json_object(text: str) -> str:
    """
    尽力从模型输出中提取 JSON 对象（{...} 或 [...]）。
    """
    s = _strip_code_fences(text)
    # 优先匹配对象 {}
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        return m.group(0).strip()
    # 其次匹配数组 []
    m = re.search(r"\[[\s\S]*\]", s)
    if m:
        return m.group(0).strip()
    return s


async def _repair_json_with_model(
    *,
    model_name: str,
    raw: str,
    llm_call,
    system_prompt: str,
) -> str:
    """
    使用同一模型做一次“只修JSON”的自修复。
    llm_call: async (messages, system_prompt) -> str
    """
    repair_instruction = (
        "你刚才输出的 JSON 不合法。请仅返回修复后的合法 JSON（不要任何解释、不要Markdown代码块）。\n\n"
        f"原始输出：\n{raw}\n"
    )
    fixed = await llm_call(messages=[{"role": "user", "content": repair_instruction}], system_prompt=system_prompt)
    return _extract_json_object(fixed)

class BusinessService:
    async def create_session(self, db: AsyncSession, user_id: int) -> Session:
        session = Session(user_id=user_id, status="active", meta_data={})
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session(self, db: AsyncSession, session_id: int) -> Session:
        result = await db.execute(select(Session).where(Session.id == session_id))
        return result.scalars().first()

    async def process_chat(self, db: AsyncSession, session_id: int, user_input: str) -> dict:
        """
        处理聊天逻辑
        Returns:
            dict: {
                "response": str,  # 展示给用户的文本
                "action": str,    # 'chat' 或 'report'
                "report_data": dict | None
            }
        """
        session = await self.get_session(db, session_id)
        if not session:
            raise ValueError("Session not found")

        # 1. 保存用户消息
        user_msg = Message(session_id=session_id, role="user", content=user_input)
        db.add(user_msg)
        await db.commit()

        # 1.1 尝试从用户输入中提取年龄/性别并落库到 Session.meta_data（便于详情页/报告复用）
        try:
            from src.utils.profile_extract import extract_age_gender

            extracted_age, extracted_gender = extract_age_gender(user_input)
            # ⚠️ 并发修复：upload-report 可能在另一请求里刚写入 attached_file_urls；
            # 这里必须 refresh 再读 meta_data，避免用“旧快照”覆盖掉附件信息，导致 ocr_text 解析不到。
            try:
                await db.refresh(session)
            except Exception:
                # refresh 失败不应阻断对话主流程
                pass

            meta = session.meta_data or {}
            updated = False

            if extracted_age is not None and meta.get("age") is None and meta.get("年龄") is None:
                meta["age"] = extracted_age
                updated = True
            if (
                extracted_gender is not None
                and meta.get("gender") is None
                and meta.get("sex") is None
                and meta.get("性别") is None
            ):
                meta["gender"] = extracted_gender
                updated = True

            if updated:
                session.meta_data = meta
                db.add(session)
                await db.commit()
        except Exception:
            # 不影响主流程：提取失败不应阻断对话
            pass

        # 2. 检查会话状态
        # 兼容旧数据：如果是字符串，转为数组
        current_tracks = session.meta_data.get("track") if session.meta_data else None
        if isinstance(current_tracks, str):
            current_tracks = [current_tracks]  # 兼容旧数据
        elif not current_tracks:
            current_tracks = []
        
        question_count = session.meta_data.get("question_count", 0) if session.meta_data else 0
        answered_count = session.meta_data.get("answered_count", 0) if session.meta_data else 0
        last_question_sent = session.meta_data.get("last_question_sent", False) if session.meta_data else False
        
        print(f"DEBUG: Before update - Tracks: {current_tracks}, Q: {question_count}, A: {answered_count}, LastSent: {last_question_sent}")

        # ⚠️ 关键修复：只有在已经发送过问题后，用户的回复才算是回答问题
        # 如果赛道已锁定、有问题计划、且上次已发送问题，说明用户刚回答了一个问题
        if current_tracks and len(current_tracks) > 0 and question_count > 0 and last_question_sent:
            answered_count += 1
            print(f"DEBUG: Updated answered_count to {answered_count}")
        
        # 检查是否已有报告（异步查询）
        report_check = await db.execute(
            select(Report).where(Report.session_id == session_id)
        )
        existing_report = report_check.scalar_one_or_none()
        
        # 判断是否应该生成报告（所有问题都回答完）
        should_generate_report = (
            current_tracks and len(current_tracks) > 0
            and not existing_report 
            and question_count > 0 
            and answered_count >= question_count
        )
        
        print(f"DEBUG: Should generate? {should_generate_report} (Existing: {bool(existing_report)})")
        
        if should_generate_report:
            # --- 生成报告阶段 ---
            
            # 1. 准备结束语（固定格式，不调用LLM）
            thank_you_msg = "收到！您的答案我们已记录。正在为您生成健康报告..."
            
            # 2. 创建空的报告记录（status = "generating"）
            new_report = Report(
                session_id=session_id,
                score=0,  # 初始值
                risk_level="生成中",  # 初始值
                content={"status": "generating", "html": ""}
            )
            db.add(new_report)
            
            # 3. 更新会话状态
            session.status = "generating_report"
            
            # 4. 保存 AI 的感谢语消息
            ai_msg = Message(session_id=session_id, role="assistant", content=thank_you_msg)
            db.add(ai_msg)
            
            await db.commit()
            await db.refresh(new_report)  # 获取 report ID
            
            # 5. 立即返回，让前端跳转
            return {
                "response": thank_you_msg,
                "action": "report",
                "report_data": {"id": new_report.id, "status": "generating"}
            }

        else:
            # --- 普通/问卷生成阶段 ---
            db_messages = await db.execute(
                select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
            )
            history_msgs = db_messages.scalars().all()
            
            api_messages = []
            for msg in history_msgs:
                api_messages.append({"role": msg.role, "content": msg.content})
            
            # 调用 LLM (对话阶段使用低思考模式)
            import time
            import logging
            logger = logging.getLogger(__name__)
            
            start_time = time.time()
            logger.info(f"[TIMING] Starting LLM call for session {session_id}...")
            
            response_text = await llm_service.chat_completion(
                messages=api_messages,
                system_prompt=PHASE_0_CHECK,
                thinking_level="low"
            )
            
            elapsed = time.time() - start_time
            logger.info(f"[TIMING] LLM call completed in {elapsed:.2f}s")
            
            # 解析思维链
            ai_thinking = ""
            user_reply = response_text
            
            if "【给用户的回复】" in response_text:
                parts = response_text.split("【给用户的回复】")
                ai_thinking = parts[0]
                user_reply = parts[1].strip()
            
            # 更新 session metadata
            # ⚠️ 并发修复：LLM 调用可能较久，期间 upload-report 可能已写入 attached_file_urls。
            # 这里先 refresh，再基于最新 meta_data 合并更新，避免覆盖掉附件信息。
            try:
                await db.refresh(session)
            except Exception:
                pass

            meta = dict(session.meta_data) if session.meta_data else {}

            # 重要：在调用 LLM 之前不要触发对 Session 的写入（SQLite 单写锁会被长时间占用）
            # 这里将 answered_count 的更新延迟到 LLM 返回后再落库，避免长时间持锁导致其他请求 500。
            meta["answered_count"] = answered_count
            
            # 检查是否锁定赛道（支持1-2个赛道）
            track_match = re.search(r"锁定赛道[:：]\s*(.+)", ai_thinking)
            if track_match:
                tracks_str = track_match.group(1).strip()
                # 解析：可能是 "赛道1, 赛道2" 或 "赛道1、赛道2" 或单个赛道
                tracks = [t.strip() for t in re.split(r'[,，、]', tracks_str) if t.strip()]
                # 限制最多2个赛道，并去重
                tracks = list(dict.fromkeys(tracks))[:2]  # 使用dict.fromkeys保持顺序并去重
                meta["track"] = tracks  # 存储为数组
            
            # 提取问题总数（仅在首次设置）
            if "question_count" not in meta or meta["question_count"] == 0:
                question_count_match = re.search(r"总问题数[:：]\s*(\d+)", ai_thinking)
                if question_count_match:
                    count = int(question_count_match.group(1))
                    # 强制最少 3 个问题
                    meta["question_count"] = max(3, count)
                    # 初始化 answered_count 为 0（还没开始回答）
                    if "answered_count" not in meta:
                        meta["answered_count"] = 0
            
            # 检测是否发送了问题（通过检测当前问题编号）
            current_question_match = re.search(r"当前问题编号[:：]\s*(\d+)", ai_thinking)
            if current_question_match:
                # 说明 AI 刚发送了一个问题，标记状态
                meta["last_question_sent"] = True
            
            # 保存 metadata
            if meta != session.meta_data:
                session.meta_data = meta
                db.add(session)
            
            # 格式化AI回复
            formatted_reply = self._format_question(user_reply)
            
            # 关键修复：检测 AI 是否自行结束了对话（即使状态机认为还没结束）
            # 如果 AI 回复中包含结束语，且已回答至少3个问题，强制进入报告生成流程
            if ("生成健康报告" in formatted_reply or "正在为您生成" in formatted_reply) and meta.get("answered_count", 0) >= 3:
                print(f"DEBUG: AI triggered completion. Text: {formatted_reply[:30]}...")
                
                # 1. 创建空的报告记录（status = "generating"）
                new_report = Report(
                    session_id=session_id,
                    score=0,  # 初始值
                    risk_level="生成中",  # 初始值
                    content={"status": "generating", "html": ""}
                )
                db.add(new_report)
                
                # 2. 更新会话状态
                session.status = "generating_report"
                
                # 3. 保存 AI 的消息
                ai_msg = Message(session_id=session_id, role="assistant", content=formatted_reply)
                db.add(ai_msg)
                
                await db.commit()
                await db.refresh(new_report)
                
                return {
                    "response": formatted_reply,
                    "action": "report",
                    "report_data": {"id": new_report.id, "status": "generating"}
                }
            
            # 保存AI回复
            ai_msg = Message(session_id=session_id, role="assistant", content=formatted_reply)
            db.add(ai_msg)
            await db.commit()
            
            return {
                "response": formatted_reply,
                "action": "chat",
                "report_data": None
            }

    def _format_question(self, response_text: str) -> str:
        """
        格式化AI回复，确保问题的选项换行
        """
        formatted = re.sub(
            r'([^\n])\s+([ABCD]\.)', 
            r'\1\n\2', 
            response_text
        )
        formatted = re.sub(
            r'(\d+\.)\s*([^\n])', 
            r'\1 \2', 
            formatted
        )
        return formatted.strip()

    async def _get_chat_history(self, db, session_id) -> str:
        result = await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
        )
        msgs = result.scalars().all()
        return "\n".join([f"{m.role}: {m.content}" for m in msgs])

    def format_questionnaire_text(self, user_messages: list[str]) -> str:
        """将用户回答格式化为“问卷文本”。

        Notes:
            - 标签提取 prompt 期望每行以“问题回答:”开头，便于模型识别。

        Args:
            user_messages: 用户消息内容列表（仅 role=user）

        Returns:
            格式化后的问卷文本
        """
        return "\n".join([f"问题回答: {msg}" for msg in user_messages if msg])

    async def _get_questionnaire_text(self, db, session_id: int) -> str:
        """获取指定会话的问卷文本（仅用户回答）。"""
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.role == "user")
            .order_by(Message.created_at)
        )
        user_msgs = result.scalars().all()
        return self.format_questionnaire_text([m.content for m in user_msgs])

    def build_report_prompt(
        self,
        *,
        user_info: str,
        track: str,
        qa_pairs: str,
        baichuan_suggestions: str,
        medical_report_ocr: Optional[str],
        max_ocr_chars: int = 8000,
    ) -> str:
        """构建报告生成阶段的 system prompt。

        Args:
            user_info: 用户基本信息
            track: 赛道（字符串展示）
            qa_pairs: 问卷/对话记录文本
            baichuan_suggestions: 专业建议文本
            medical_report_ocr: 体检报告OCR整理文本（可为空）
            max_ocr_chars: OCR文本最大注入字符数（避免prompt过长）

        Returns:
            拼装后的报告生成 system prompt
        """
        ocr_text = (medical_report_ocr or "").strip()
        if ocr_text and len(ocr_text) > max_ocr_chars:
            ocr_text = ocr_text[:max_ocr_chars] + "…（内容较长已截断）"

        return REPORT_GENERATION.format(
            user_info=user_info,
            track=track,
            qa_pairs=qa_pairs,
            medical_report_ocr=ocr_text or "（未上传体检报告或未解析到OCR文本）",
            baichuan_suggestions=baichuan_suggestions or "（无专业建议）",
        )

    async def generate_report_content(self, db: AsyncSession, session_id: int):
        """生成报告内容（LLM调用）"""
        # 获取 session 和 report
        session = await self.get_session(db, session_id)
        if not session:
            raise ValueError("Session not found")
        
        report_result = await db.execute(
            select(Report).where(Report.session_id == session_id)
        )
        report = report_result.scalar_one_or_none()
        if not report:
            raise ValueError("Report not found")
        
        # 检查是否已生成
        if report.content.get("status") != "generating":
            return  # 已生成，无需重复
        
        try:
            prompts = load_report_prompts()
            html_template = load_report_html_template()

            # 获取历史消息（完整对话）与问卷文本（仅用户回答）
            history = await self._get_chat_history(db, session_id)
            questionnaire_text = await self._get_questionnaire_text(db, session_id)
            # 兼容旧数据：如果是字符串，转为数组
            current_tracks = session.meta_data.get("track", [])
            if isinstance(current_tracks, str):
                current_tracks = [current_tracks]  # 兼容旧数据
            elif not current_tracks:
                current_tracks = []
            
            # 转换为字符串格式（用于传递给百川和报告生成）
            track_str = "、".join(current_tracks) if current_tracks else "未知"
            
            user_info = session.meta_data.get("user_info", "未提取")
            ocr_text = (getattr(session, "ocr_text", None) or "").strip()

            import logging
            logger = logging.getLogger("healthy_rag")

            # ========== Stage A：百川输出结构化JSON ==========
            baichuan_input = (
                f"用户健康档案（基础信息）：{user_info}\n"
                f"锁定赛道：{track_str}\n\n"
                f"【问卷回答】\n{questionnaire_text or '（无）'}\n\n"
                f"【图片/PDF解析内容】\n{ocr_text or '（未上传或未解析到文本）'}\n"
            )
            logger.info("StageA(Baichuan) generating report JSON session=%s ...", session_id)
            baichuan_raw = await baichuan_service.generate_json_by_prompt(
                prompt=prompts.baichuan,
                input_text=baichuan_input,
                temperature=0.1,
                max_tokens=4096,
            )
            baichuan_json_text = _extract_json_object(baichuan_raw)
            try:
                baichuan_json = json.loads(baichuan_json_text)
            except Exception:
                baichuan_json_text = await _repair_json_with_model(
                    model_name="baichuan",
                    raw=baichuan_raw,
                    llm_call=lambda messages, system_prompt: baichuan_service.generate_json_by_prompt(
                        prompt=system_prompt, input_text=messages[0]["content"], temperature=0.1, max_tokens=4096
                    ),
                    system_prompt=prompts.baichuan,
                )
                baichuan_json = json.loads(baichuan_json_text)

            # 兼容旧字段：把百川JSON字符串也塞到 baichuan_suggestions
            report.baichuan_suggestions = json.dumps(baichuan_json, ensure_ascii=False)
            report.content = {
                "status": "generating",
                "html": "",
                "baichuan_json": baichuan_json,
                "deepseek_json": None,
                "merged_json": None,
            }
            db.add(report)
            await db.commit()

            # ========== 仍保留：问卷完成时提取健康标签（无OCR也可） ==========
            # 目的：即使用户未上传体检报告，也能从问卷/主诉中得到如“鼻塞”等标准标签
            try:
                existing_tags = session.ocr_tags or []
                if not existing_tags:
                    tags = await baichuan_service.extract_tags_from_ocr_and_questionnaire(
                        ocr_text=(getattr(session, "ocr_text", None) or ""),
                        questionnaire_text=questionnaire_text,
                    )
                    if tags:
                        # 去重保持顺序
                        merged = list(dict.fromkeys(existing_tags + tags))
                        session.ocr_tags = merged
                        db.add(session)
                        logger.info(
                            "Extracted questionnaire tags for session %s: %s",
                            session_id,
                            merged,
                        )
                    else:
                        logger.info(
                            "No questionnaire tags extracted for session %s",
                            session_id,
                        )
            except Exception as e:
                logger.warning(
                    "Questionnaire tag extraction failed for session %s: %s",
                    session_id,
                    str(e),
                )

            # ========== Stage B：Deepseek 细化补全 ==========
            logger.info("StageB(Deepseek) refining JSON session=%s ...", session_id)
            deepseek_input = (
                f"用户原始数据：\n"
                f"- 用户信息：{user_info}\n"
                f"- 锁定赛道：{track_str}\n"
                f"- 问卷回答：\n{questionnaire_text or '（无）'}\n"
                f"- 图片/PDF解析内容：\n{ocr_text or '（无）'}\n\n"
                f"百川 JSON：\n{json.dumps(baichuan_json, ensure_ascii=False)}\n"
            )
            deepseek_raw = await llm_service.deepseek_completion(
                messages=[{"role": "user", "content": deepseek_input}],
                system_prompt=prompts.deepseek,
                model=llm_service.ds_chat_model,
                temperature=0.7,
            )
            deepseek_json_text = _extract_json_object(deepseek_raw)
            try:
                deepseek_json = json.loads(deepseek_json_text)
            except Exception:
                deepseek_json_text = await _repair_json_with_model(
                    model_name="deepseek",
                    raw=deepseek_raw,
                    llm_call=lambda messages, system_prompt: llm_service.deepseek_completion(
                        messages=messages, system_prompt=system_prompt, model=llm_service.ds_chat_model, temperature=0.7
                    ),
                    system_prompt=prompts.deepseek,
                )
                deepseek_json = json.loads(deepseek_json_text)

            report.content = {
                **(report.content or {}),
                "deepseek_json": deepseek_json,
            }
            db.add(report)
            await db.commit()

            # ========== Stage C：Gemini 聚合JSON + 注入固定模板生成HTML ==========
            import time as _time
            stage_c_start = _time.time()
            logger.info("StageC(Gemini) composing final HTML session=%s ...", session_id)
            gemini_system = (
                f"{prompts.gemini}\n\n"
                "【固定HTML模板】\n"
                "你必须严格参考并填充以下模板结构，不要改变DOM结构与class命名，仅替换内容与重复区块的数据。\n"
                "模板：\n"
                f"{html_template}\n\n"
                "【输出要求补充】\n"
                "只输出完整HTML（以 <!DOCTYPE html> 或 <html 开头）。不要输出任何JSON，不要插入解释文字。\n"
            )
            gemini_user = (
                "Baichuan JSON：\n"
                f"{json.dumps(baichuan_json, ensure_ascii=False)}\n\n"
                "DeepSeek JSON：\n"
                f"{json.dumps(deepseek_json, ensure_ascii=False)}\n"
            )

            class _EmptyReportHtmlError(Exception):
                """Stage C 返回空 HTML 的可重试错误。"""

            async def _stage_c_parse_llm_output(*, raw_text: str) -> tuple[str, dict]:
                raw_clean = _strip_code_fences(raw_text)
                html_idx = find_html_start_index(raw_clean)
                if html_idx != -1:
                    json_part_raw = raw_clean[:html_idx].strip()
                    html_part = raw_clean[html_idx:].strip()

                    # 允许模型只输出 HTML（无前置 JSON），此时使用兜底 merged_json
                    if not json_part_raw:
                        merged = {
                            "baichuan": baichuan_json,
                            "deepseek": deepseek_json,
                        }
                    else:
                        json_part = _extract_json_object(json_part_raw)
                        try:
                            merged = json.loads(json_part)
                        except Exception:
                            # 用 Gemini 做一次 JSON 修复（不重跑HTML）
                            fixed_json_text = await _repair_json_with_model(
                                model_name="gemini",
                                raw=json_part,
                                llm_call=lambda messages, system_prompt: llm_service.gemini_completion(
                                    messages=messages,
                                    system_prompt=system_prompt,
                                    thinking_level="high",
                                    temperature=0.3,
                                ),
                                system_prompt="你是JSON修复器。只返回修复后的合法JSON对象。",
                            )
                            merged = json.loads(fixed_json_text)
                    final = html_part
                else:
                    # 兜底：找不到任何 HTML 起点，尽力剥离“前置JSON”，避免 JSON 被渲染
                    final, parsed = strip_leading_json(raw_clean)
                    merged = parsed if isinstance(parsed, dict) else {
                        "baichuan": baichuan_json,
                        "deepseek": deepseek_json,
                    }

                if not (final or "").strip():
                    raise _EmptyReportHtmlError("Empty HTML")
                return final, merged

            async def _stage_c_gemini_once(*, attempt: int) -> tuple[str, dict]:
                start = _time.time()
                gemini_raw = await llm_service.gemini_completion(
                    messages=[{"role": "user", "content": gemini_user}],
                    system_prompt=gemini_system,
                    thinking_level="high",
                    temperature=0.7,
                    max_tokens=8000,
                )
                elapsed = _time.time() - start
                logger.info(
                    "StageC(Gemini) attempt=%s completed in %.1fs, raw_length=%d session=%s",
                    attempt,
                    elapsed,
                    len(gemini_raw or ""),
                    session_id,
                )
                return await _stage_c_parse_llm_output(raw_text=gemini_raw)

            # 规则：Gemini 生成 HTML 为空时，再用 Gemini 重试一次；仍失败则 fallback 到 DeepSeek
            final_html = ""
            merged_json: dict = {}
            try:
                final_html, merged_json = await _stage_c_gemini_once(attempt=1)
            except _EmptyReportHtmlError:
                logger.warning(
                    "StageC(Gemini) returned empty HTML, retrying once session=%s",
                    session_id,
                )
                try:
                    final_html, merged_json = await _stage_c_gemini_once(attempt=2)
                except _EmptyReportHtmlError:
                    logger.warning(
                        "StageC(Gemini) still empty after retry, falling back to DeepSeek session=%s",
                        session_id,
                    )
                    deepseek_raw = await llm_service.deepseek_completion(
                        messages=[{"role": "user", "content": gemini_user}],
                        system_prompt=gemini_system,
                        model=llm_service.ds_reasoner_model,
                        temperature=None,
                        max_tokens=8000,
                    )
                    # DeepSeek 输出大概率只有 HTML；但仍复用同一解析逻辑，允许“前置 JSON”场景
                    final_html, merged_json = await _stage_c_parse_llm_output(
                        raw_text=deepseek_raw
                    )
                    logger.info(
                        "StageC(DeepSeek) fallback succeeded, raw_length=%d session=%s",
                        len(deepseek_raw or ""),
                        session_id,
                    )
            except Exception as gemini_err:
                stage_c_elapsed = _time.time() - stage_c_start
                logger.error(
                    "StageC(Gemini) FAILED after %.1fs session=%s: %s",
                    stage_c_elapsed,
                    session_id,
                    str(gemini_err),
                )
                raise

            # 更新报告（以 JSON 为准，不再从HTML正则提取）
            from datetime import datetime, timezone
            report.score = int(baichuan_json.get("score", 0) or 0)
            from src.utils.risk import normalize_risk_level

            report.risk_level = normalize_risk_level(baichuan_json.get("risk_level"))
            report.content = {
                "status": "completed",
                "html": final_html,
                "baichuan_json": baichuan_json,
                "deepseek_json": deepseek_json,
                "merged_json": merged_json,
            }
            # 使用带时区的时间，确保前端能正确转换为本地时间
            report.created_at = datetime.now(timezone.utc)
            
            # 更新会话状态
            session.status = "completed"
            # 报告生成完后，清空“上传文件URL”（避免新对话/后续页面仍显示已上传）
            # 说明：保留 ocr_text/ocr_tags 以支持报告页展示与推荐；如需更强隐私清理，可再扩展策略。
            session.uploaded_file_url = None
            
            db.add(report)
            db.add(session)
            await db.commit()
            
        except Exception as e:
            # 生成失败，标记错误
            report.content = {"status": "error", "error": str(e), "html": ""}
            db.add(report)
            await db.commit()
            raise

business_service = BusinessService()
