import httpx
from typing import List
from src.config.settings import settings

class VolcService:
    """火山引擎服务类."""
    
    def __init__(self):
        self.api_key = settings.VOLC_API_KEY
        self.model = settings.VOLC_EMBEDDING_MODEL
        self.base_url = settings.VOLC_API_BASE
        
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本向量 embeddings."""
        if not texts:
            return []
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Volcengine API Error: {response.text}")
                
            data = response.json()
            return [item["embedding"] for item in data["data"]]

