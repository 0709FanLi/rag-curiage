"""
产品推荐服务
根据用户的赛道和OCR提取的标签，匹配合适的产品推荐规则
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.tables.chat import ProductRule

logger = logging.getLogger(__name__)


class ProductRecommendationService:
    """产品推荐服务类"""
    
    def __init__(self):
        pass
    
    async def recommend_products(
        self,
        db: AsyncSession,
        tracks: List[str],  # 改为支持多个赛道
        user_tags: List[str],
        max_recommendations: int = 3
    ) -> List[Dict[str, Any]]:
        """
        根据赛道和用户标签推荐产品
        
        匹配逻辑（参考 docs/匹配逻辑.md）：
        1. 第一步：赛道锁定 - 只在指定赛道内查找
        2. 第二步：标签匹配 - 用户标签与规则触发标签的交集
        3. 第三步：优先级处理 - 优先返回高风险规则
        4. 第四步：兜底匹配 - 如果没有匹配到，返回该赛道的低风险兜底规则
        
        Args:
            db: 数据库会话
            tracks: 用户的赛道列表（1-2个赛道）
            user_tags: 用户的标签列表（从OCR提取）
            max_recommendations: 最多返回的推荐数量
        
        Returns:
            推荐产品列表，每个产品包含规则信息和产品详情
        """
        # 兼容旧数据：如果是字符串，转为列表
        if isinstance(tracks, str):
            tracks = [tracks]
        elif not tracks:
            tracks = []
        
        logger.info(f"开始产品推荐匹配 - 赛道: {tracks}, 标签: {user_tags}")
        
        # 标准化所有赛道名称（处理不同格式）
        normalized_tracks = [self._normalize_track_name(t) for t in tracks]
        logger.info(f"标准化后的赛道: {normalized_tracks}")
        
        if not normalized_tracks:
            logger.warning("没有有效的赛道，无法推荐产品")
            return []
        
        # 步骤1: 获取这些赛道的所有规则
        result = await db.execute(
            select(ProductRule).where(ProductRule.track.in_(normalized_tracks))
        )
        rules = result.scalars().all()
        
        if not rules:
            logger.warning(f"未找到赛道 {normalized_tracks} 的任何产品规则")
            return []
        
        logger.info(f"找到 {len(rules)} 条规则")
        
        # 步骤2: 标签匹配，计算每个规则的匹配度
        matched_rules = []
        
        for rule in rules:
            trigger_tags = rule.trigger_tags or []
            
            # 计算交集 - 只要有一个用户标签在触发标签中，就算匹配
            matched_tags = set(user_tags) & set(trigger_tags)
            
            if matched_tags:
                matched_rules.append({
                    "rule": rule,
                    "matched_tags": list(matched_tags),
                    "match_count": len(matched_tags)
                })
        
        # 步骤3: 优先级排序
        # 按照：风险等级（高>中>低）> 匹配标签数 > 规则ID
        risk_priority = {"高": 3, "中": 2, "低": 1}
        
        matched_rules.sort(
            key=lambda x: (
                risk_priority.get(x["rule"].risk_level, 0),
                x["match_count"],
                x["rule"].rule_id
            ),
            reverse=True
        )
        
        # 步骤4: 兜底匹配逻辑（为每个赛道查找兜底规则）
        if not matched_rules:
            logger.info(f"没有匹配到任何规则，使用兜底规则（低风险）")
            # 为每个赛道查找兜底规则（rule_id 以 -03 结尾）
            for normalized_track in normalized_tracks:
                fallback_rule = next(
                    (r for r in rules if r.track == normalized_track and r.rule_id.endswith("-03")),
                    None
                )
                
                if fallback_rule:
                    matched_rules.append({
                        "rule": fallback_rule,
                        "matched_tags": [],
                        "match_count": 0
                    })
                    logger.info(f"使用兜底规则: {fallback_rule.rule_id} (赛道: {normalized_track})")
        
        # 返回前 N 个推荐
        recommendations = []
        for item in matched_rules[:max_recommendations]:
            rule = item["rule"]
            recommendation = {
                "rule_id": rule.rule_id,
                "track": rule.track,
                "risk_level": rule.risk_level,
                "matched_tags": item["matched_tags"],
                "product_info": rule.product_info,  # 包含产品名称、描述、图片等
                # pro-table 逻辑字段（若已同步入库，可用于前端展示/电商搜索/后续复用）
                "match_key": getattr(rule, "match_key", None),
                "toc_search_query": getattr(rule, "toc_search_query", None),
                "core_ingredient_name": getattr(rule, "core_ingredient_name", None),
                "ai_talk_script": getattr(rule, "ai_talk_script", None),
                "buying_tip": getattr(rule, "buying_tip", None),
            }
            recommendations.append(recommendation)
        
        logger.info(f"返回 {len(recommendations)} 个推荐产品")
        return recommendations
    
    def _normalize_track_name(self, track: str) -> str:
        """
        标准化赛道名称
        处理不同格式的赛道名称，统一为数据库中的标准格式
        
        Args:
            track: 原始赛道名称
        
        Returns:
            标准化后的赛道名称
        """
        # 移除数字前缀、括号、"赛道"等后缀
        track = track.strip()
        track = track.replace("赛道", "").strip()
        
        # 定义赛道关键词到标准名称的映射
        track_mapping = {
            "神经系统": "神经系统",
            "神经": "神经系统",
            "消化系统": "消化系统",
            "消化": "消化系统",
            "免疫与出血": "免疫与出血",
            "免疫": "免疫与出血",
            "血液": "免疫与出血",
            "心血管": "心血管",
            "心脏": "心血管",
            "皮肤": "皮肤",
            "内分泌": "内分泌",
            "骨骼与代谢": "骨骼与代谢",
            "骨骼": "骨骼与代谢",
            "代谢": "骨骼与代谢",
        }
        
        # 尝试精确匹配
        if track in track_mapping:
            return track_mapping[track]
        
        # 尝试关键词匹配
        for keyword, standard_name in track_mapping.items():
            if keyword in track:
                return standard_name
        
        # 如果没有匹配到，返回原名称
        logger.warning(f"无法标准化赛道名称: {track}")
        return track
    
    async def get_recommended_products_by_session(
        self,
        db: AsyncSession,
        session_id: int
    ) -> List[Dict[str, Any]]:
        """
        根据 session_id 获取推荐产品
        从 session 中读取赛道和标签，然后进行推荐
        
        Args:
            db: 数据库会话
            session_id: 会话ID
        
        Returns:
            推荐产品列表
        """
        from src.models.tables.chat import Session
        
        # 获取 session
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.error(f"Session {session_id} not found")
            return []
        
        # 获取赛道和标签（兼容旧数据）
        tracks = session.meta_data.get("track", [])
        if isinstance(tracks, str):
            tracks = [tracks]  # 兼容旧数据
        elif not tracks:
            tracks = []
        
        user_tags = session.ocr_tags or []
        
        logger.info(f"Session {session_id} - Tracks: {tracks}, Tags: {user_tags}")
        
        # 如果没有OCR标签，尝试使用空标签（会触发兜底规则）
        if not user_tags:
            logger.info("No OCR tags found, will use fallback rule")
        
        # 调用推荐逻辑
        return await self.recommend_products(db, tracks, user_tags)


# 创建全局实例
product_recommendation_service = ProductRecommendationService()

