"""
文件上传API路由
支持上传图片和PDF文件到阿里云OSS
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from src.services.oss_service import OSSService
from src.api.dependencies import get_current_user
from src.models.tables.user import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
oss_service = OSSService()


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    上传文件到OSS
    
    支持的文件类型：
    - 图片: jpg, jpeg, png
    - 文档: pdf
    
    Args:
        file: 上传的文件
        current_user: 当前登录用户
    
    Returns:
        {
            "success": true,
            "file_url": "https://...",
            "file_name": "xxx.jpg",
            "file_size": 12345,
            "content_type": "image/jpeg"
        }
    """
    try:
        # 验证文件类型
        allowed_types = {
            "image/jpeg", "image/jpg", "image/png",
            "application/pdf"
        }
        
        content_type = file.content_type
        
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {content_type}。仅支持 JPG, PNG, PDF"
            )
        
        # 验证文件大小 (最大 50MB)
        file_content = await file.read()
        file_size = len(file_content)
        max_size = 50 * 1024 * 1024  # 50MB
        
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大: {file_size / 1024 / 1024:.2f}MB。最大支持 50MB"
            )
        
        logger.info(
            f"用户 {current_user.username} 上传文件: "
            f"{file.filename} ({file_size / 1024:.2f}KB, {content_type})"
        )
        
        # 上传到OSS
        result = oss_service.upload_file(
            file_data=file_content,
            filename=file.filename,
            category="medical_reports",  # 分类存储
            content_type=content_type
        )
        
        logger.info(f"文件上传成功: {result['url']}")
        
        return {
            "success": True,
            "file_url": result["url"],
            "file_name": file.filename,
            "file_size": file_size,
            "content_type": content_type,
            "object_key": result["object_key"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败: {str(e)}"
        )

