from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
import json

from src.api.dependencies import get_db
from src.models.tables.knowledge import KnowledgeFile, KBType, FileStatus
from src.services.knowledge_service import KnowledgeService
from src.services.oss_service import OSSService
from src.services.vector_service import VectorService
from src.services.volc_service import VolcService
from pydantic import BaseModel

router = APIRouter()

# --- Schemas ---
class FileResponse(BaseModel):
    id: int
    filename: str
    oss_url: Optional[str]
    kb_type: str
    tags: List[str]
    status: str
    error_msg: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

class FileListResponse(BaseModel):
    total: int
    files: List[FileResponse]

class SearchRequest(BaseModel):
    query: str
    kb_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    limit: int = 5

class SearchResult(BaseModel):
    content: str
    doc_id: int
    kb_type: str
    source: str
    distance: float

# --- Helpers ---
def map_status(status: FileStatus, kb_type: KBType) -> str:
    """Maps backend status to frontend display status."""
    if status == FileStatus.completed:
        if kb_type == KBType.safety:
            return "已生效"
        elif kb_type == KBType.science:
            return "已学习"
        elif kb_type == KBType.product:
            return "已关联"
        else:
            return "已完成"
    elif status in [FileStatus.uploading, FileStatus.processing]:
        return "AI学习中..."
    elif status == FileStatus.failed:
        return "处理失败"
    else:
        return status.value

# --- Endpoints ---

@router.post("/upload", response_model=FileResponse)
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    kb_type: KBType = Form(...),
    tags: str = Form(default="[]"), # JSON string
    db: AsyncSession = Depends(get_db)
):
    """上传知识文件."""
    try:
        tags_list = json.loads(tags)
    except:
        tags_list = []

    # 1. 上传到 OSS
    oss = OSSService()
    file_content = await file.read()
    
    # 使用 BytesIO 包装以便 OSS SDK 读取
    import io
    file_obj = io.BytesIO(file_content)
    
    try:
        upload_result = oss.upload_file(
            file_data=file_obj,
            filename=file.filename,
            category=f"knowledge/{kb_type.value}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OSS Upload Failed: {str(e)}")

    # 2. 创建数据库记录
    new_file = KnowledgeFile(
        filename=file.filename,
        object_key=upload_result["object_key"],
        oss_url=upload_result["url"],
        kb_type=kb_type,
        tags=tags_list,
        status=FileStatus.uploading
    )
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)

    # 3. 触发后台处理任务
    service = KnowledgeService(db)
    background_tasks.add_task(service.process_file_background, new_file.id)

    # Map status for response
    display_status = map_status(new_file.status, new_file.kb_type)

    return FileResponse(
        id=new_file.id,
        filename=new_file.filename,
        oss_url=new_file.oss_url,
        kb_type=new_file.kb_type.value,
        tags=new_file.tags,
        status=display_status,
        error_msg=new_file.error_msg,
        created_at=new_file.created_at.isoformat()
    )

@router.get("/files", response_model=FileListResponse)
async def list_files(
    page: int = 1,
    page_size: int = 10,
    kb_type: Optional[KBType] = None,
    status: Optional[FileStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取文件列表 (分页，按文件名去重保留最新)."""
    # 使用子查询来去重：对每个 (kb_type, filename) 分组，取最大的 id (最新)
    # 注意：这里我们假设同名文件在同 KB 下应被视为更新版本。
    # 如果跨 KB 同名，可能需要仅按 filename 分组。根据用户语境 "列表中不应该出现两个文档记录"，通常指文件名唯一。
    
    subquery = select(
        func.max(KnowledgeFile.id).label("max_id")
    ).group_by(KnowledgeFile.filename) # 严格按文件名去重
    
    # 如果有 kb_type 筛选，子查询也要加上，否则 max_id 可能指向被过滤掉的记录
    if kb_type:
        subquery = subquery.where(KnowledgeFile.kb_type == kb_type)
    if status:
        subquery = subquery.where(KnowledgeFile.status == status)
    
    # 主查询：只查 ID 在子查询中的记录
    query = select(KnowledgeFile).where(KnowledgeFile.id.in_(subquery))
    
    # 计算总数 (去重后)
    # 注意：Scalar subquery for count
    count_subquery = select(func.count(func.distinct(KnowledgeFile.filename)))
    if kb_type:
        count_subquery = count_subquery.where(KnowledgeFile.kb_type == kb_type)
    if status:
        count_subquery = count_subquery.where(KnowledgeFile.status == status)
    
    total = await db.scalar(count_subquery) or 0
    
    # 分页和排序
    query = query.order_by(desc(KnowledgeFile.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
        
    result = await db.execute(query)
    files = result.scalars().all()
    
    # 转换并映射状态
    response_files = []
    for f in files:
        display_status = map_status(f.status, f.kb_type)
        response_files.append(FileResponse(
            id=f.id,
            filename=f.filename,
            oss_url=f.oss_url,
            kb_type=f.kb_type.value,
            tags=f.tags,
            status=display_status,
            error_msg=f.error_msg,
            created_at=f.created_at.isoformat()
        ))
    
    return FileListResponse(
        total=total,
        files=response_files
    )

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除文件."""
    result = await db.execute(select(KnowledgeFile).where(KnowledgeFile.id == file_id))
    file_record = result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
        
    # 1. 删除 OSS 文件
    oss = OSSService()
    try:
        oss.delete_file(file_record.object_key)
    except Exception as e:
        print(f"Warning: Failed to delete OSS file: {e}")

    # 2. 删除 Weaviate 向量
    vector = VectorService()
    try:
        vector.delete_by_doc_id(file_id)
    except Exception as e:
        print(f"Warning: Failed to delete vectors: {e}")

    # 3. 删除数据库记录
    await db.delete(file_record)
    await db.commit()
    
    return {"message": "File deleted successfully"}

@router.post("/search", response_model=List[SearchResult])
async def search_knowledge(
    request: SearchRequest
):
    """向量检索."""
    # 1. 获取 Query Embedding
    volc = VolcService()
    try:
        embeddings = await volc.get_embeddings([request.query])
        query_vector = embeddings[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding Error: {str(e)}")
        
    # 2. 构建过滤条件
    import weaviate.classes.query as wq
    filters = None
    
    conditions = []
    if request.kb_types:
        # 知识库类型过滤 (OR)
        kb_conditions = []
        for kb in request.kb_types:
            kb_conditions.append(wq.Filter.by_property("kb_type").equal(kb))
        if len(kb_conditions) > 1:
            conditions.append(wq.Filter.any_of(kb_conditions))
        elif len(kb_conditions) == 1:
            conditions.append(kb_conditions[0])
            
    if request.tags:
        # 标签过滤 (OR - 只要包含任一标签即可，也可以根据需求改为 AND)
        # Weaviate 数组包含检查
        tag_conditions = []
        for tag in request.tags:
            # 注意：Weaviate 现在的 filter API 对 array 比较支持可能有限，
            # 这里假设使用 text_array 类型的 contains_any
            # 但 python client v4 语法可能不同，这里使用简单的 equal 尝试 (通常对 array 意味着 contains)
            tag_conditions.append(wq.Filter.by_property("tags").contains_any([tag]))
        
        if len(tag_conditions) > 1:
            conditions.append(wq.Filter.any_of(tag_conditions))
        elif len(tag_conditions) == 1:
            conditions.append(tag_conditions[0])
    
    if len(conditions) > 1:
        filters = wq.Filter.all_of(conditions)
    elif len(conditions) == 1:
        filters = conditions[0]

    # 3. 执行检索
    vector = VectorService()
    try:
        results = vector.search(
            query_vector=query_vector,
            limit=request.limit,
            filters=filters
        )
        vector.close() # 记得关闭连接，或者使用单例模式管理连接
        return results
    except Exception as e:
        vector.close()
        raise HTTPException(status_code=500, detail=f"Vector Search Error: {str(e)}")
