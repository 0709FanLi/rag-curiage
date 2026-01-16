import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Healthy RAG"
    API_V1_STR: str = "/api/v1"
    
    # Upload / OCR limits
    # 单次体检报告解析（多图）最大图片张数
    MAX_OCR_IMAGES: int = 10
    # 单次批次内 PDF 总大小上限（MB）
    MAX_PDF_TOTAL_MB_PER_BATCH: int = 50
    # 单个 PDF 最大页数
    MAX_PDF_PAGES: int = 50

    # Security
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE_PLEASE_CHANGE"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Database
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/healthy.db"
    
    # AI
    DEEP_SEEK_API_KEY: Optional[str] = Field(default=None, alias="DEEP_SEEK") 
    DEEP_SEEK_MODEL_REASONER: str = "deepseek-reasoner"
    DEEP_SEEK_TIMEOUT: int = 300

    # Gemini (GRSAI)
    GEMINI_API_KEY: Optional[str] = Field(default=None, alias="GRSAI_KEY")
    GEMINI_BASE_URL: str = "https://grsai.dakka.com.cn/v1"
    GEMINI_MODEL: str = "gemini-3-pro"
    GEMINI_TIMEOUT: int = 300

    # Baichuan (百川智能)
    BAICHUAN_API_KEY: Optional[str] = Field(default=None, alias="BAICHUAN_API_KEY")
    BAICHUAN_BASE_URL: str = "https://api.baichuan-ai.com/v1"
    BAICHUAN_MODEL: str = "Baichuan-M2-Plus"
    BAICHUAN_TIMEOUT: int = 300

    # Qwen VL (通义千问视觉理解)
    DASHSCOPE_API_KEY: Optional[str] = Field(default=None, alias="DASHSCOPE_API_KEY")
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_LONG_MODEL: str = "qwen-long"

    # Volcengine (火山引擎)
    # 优先匹配 ARK_API_KEY
    VOLC_API_KEY: Optional[str] = Field(default=None, validation_alias="ARK_API_KEY")
    VOLC_EMBEDDING_MODEL: str = "ep-m-20251125184146-lsgvz"
    VOLC_API_BASE: str = "https://ark.cn-beijing.volces.com/api/v3"

    # Weaviate
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None

    # Aliyun OSS
    OSS_ACCESS_KEY_ID: Optional[str] = None
    OSS_ACCESS_KEY_SECRET: Optional[str] = None
    OSS_BUCKET_NAME: Optional[str] = None
    OSS_ENDPOINT: str = "https://oss-cn-shanghai.aliyuncs.com"
    OSS_PUBLIC_READ: bool = True

    # SMTP（邮箱验证码）
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_SSL: bool = False
    SMTP_STARTTLS: bool = True

    # 邮箱验证码（OTP）参数
    EMAIL_OTP_EXPIRE_MINUTES: int = 10
    EMAIL_OTP_COOLDOWN_SECONDS: int = 60
    EMAIL_OTP_MAX_PER_HOUR: int = 5

    class Config:
        # 读取 .env
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"
        populate_by_name = True 

settings = Settings()
