from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from src.models.database import Base
import enum

class KBType(str, enum.Enum):
    safety = "safety"
    science = "science"
    product = "product"

class FileStatus(str, enum.Enum):
    uploading = "uploading"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class KnowledgeFile(Base):
    __tablename__ = "knowledge_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    object_key = Column(String, nullable=False)
    oss_url = Column(String, nullable=True)
    kb_type = Column(SQLEnum(KBType), nullable=False)
    tags = Column(JSON, default=[])  # Store as JSON array
    status = Column(SQLEnum(FileStatus), default=FileStatus.uploading)
    error_msg = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

