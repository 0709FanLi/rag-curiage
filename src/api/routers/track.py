from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import re

router = APIRouter()

# --- Schemas ---
class TrackInfo(BaseModel):
    name: str
    display_name: str
    description: str
    color: str
    keywords: List[str]

class TrackDetectionRequest(BaseModel):
    text: str
    max_tracks: int = 2

class TrackDetectionResponse(BaseModel):
    tracks: List[str]
    confidence: float

# --- 赛道配置 ---
TRACK_CONFIGS = {
    "消化赛道": {
        "display_name": "消化赛道",
        "description": "涉及胃肠道健康、消化系统相关问题",
        "color": "bg-success",
        "keywords": ['消化', '胃', '肠道', '肠', '便秘', '腹泻', '胀气', '口臭']
    },
    "骨骼与代谢赛道": {
        "display_name": "骨骼与代谢赛道",
        "description": "涉及骨骼健康、代谢系统、关节问题",
        "color": "bg-info",
        "keywords": ['骨骼', '代谢', '关节', '腰酸', '背痛', '痛风', '肥胖', '体重', '乏力']
    },
    "神经赛道": {
        "display_name": "神经赛道",
        "description": "涉及神经系统、睡眠、情绪相关问题",
        "color": "bg-primary",
        "keywords": ['神经', '失眠', '睡眠', '多梦', '压力', '头痛', '记忆', '焦虑', '情绪', '抑郁']
    },
    "免疫及血液赛道": {
        "display_name": "免疫及血液赛道",
        "description": "涉及免疫系统、血液健康、术后恢复",
        "color": "bg-danger",
        "keywords": ['免疫', '血液', '感冒', '过敏', '贫血', '虚弱', '术后', '恢复']
    },
    "内分泌赛道": {
        "display_name": "内分泌赛道",
        "description": "涉及内分泌系统、激素相关问题",
        "color": "bg-secondary",
        "keywords": ['内分泌', '月经', '更年期', '甲状腺', '潮热']
    },
    "皮肤赛道": {
        "display_name": "皮肤赛道",
        "description": "涉及皮肤健康、抗衰老相关问题",
        "color": "bg-warning",
        "keywords": ['皮肤', '痤疮', '色斑', '皱纹', '干燥', '出油', '抗衰', '抗衰老']
    },
    "心血管赛道": {
        "display_name": "心血管赛道",
        "description": "涉及心血管健康、血压血脂问题",
        "color": "bg-dark",
        "keywords": ['心血管', '心慌', '胸闷', '血压', '血脂', '手脚冰凉']
    }
}

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
    standard_tracks = list(TRACK_CONFIGS.keys())
    if track_name in standard_tracks:
        return track_name

    # 默认返回"其他"
    return "其他"

def detect_tracks_from_text(text: str, max_tracks: int = 2) -> List[str]:
    """
    从文本中检测可能的赛道

    Args:
        text: 输入文本
        max_tracks: 最多返回的赛道数量

    Returns:
        赛道名称列表
    """
    if not text or not isinstance(text, str):
        return []

    text = text.lower()
    matched_tracks = []

    # 计算每个赛道的匹配分数
    track_scores = {}
    for track_name, config in TRACK_CONFIGS.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword.lower() in text:
                score += 1
        if score > 0:
            track_scores[track_name] = score

    # 按分数排序，取前max_tracks个
    sorted_tracks = sorted(track_scores.items(), key=lambda x: x[1], reverse=True)
    matched_tracks = [track for track, score in sorted_tracks[:max_tracks]]

    return matched_tracks

@router.get("/tracks", response_model=List[TrackInfo])
async def get_tracks():
    """
    获取所有可用赛道列表

    返回包含赛道名称、显示名称、描述、颜色和关键词的完整信息
    """
    tracks = []
    for track_name, config in TRACK_CONFIGS.items():
        tracks.append(TrackInfo(
            name=track_name,
            display_name=config["display_name"],
            description=config["description"],
            color=config["color"],
            keywords=config["keywords"]
        ))
    return tracks

@router.post("/detect", response_model=TrackDetectionResponse)
async def detect_track(request: TrackDetectionRequest):
    """
    根据输入文本检测可能的赛道

    - **text**: 要分析的文本内容
    - **max_tracks**: 最多返回的赛道数量（默认2个）
    """
    tracks = detect_tracks_from_text(request.text, request.max_tracks)

    # 计算置信度（基于匹配到的关键词数量）
    confidence = min(len(tracks) * 0.5, 1.0) if tracks else 0.0

    return TrackDetectionResponse(
        tracks=tracks,
        confidence=confidence
    )

@router.post("/normalize")
async def normalize_track(track_name: str):
    """
    标准化赛道名称

    将各种变体或别名映射到标准赛道名称

    - **track_name**: 需要标准化的赛道名称
    """
    normalized = normalize_track_name(track_name)
    return {
        "original": track_name,
        "normalized": normalized
    }
