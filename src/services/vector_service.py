import weaviate
import weaviate.classes.config as config
from src.config.settings import settings
from typing import List, Dict, Any, Optional

class VectorService:
    """Weaviate 向量数据库服务类."""
    
    def __init__(self):
        # 解析 WEAVIATE_URL，如果在 Docker 中应该使用容器名 (如 healthy-rag-weaviate)
        weaviate_url = settings.WEAVIATE_URL.replace("http://", "").replace("https://", "")
        
        if ":" in weaviate_url:
            host = weaviate_url.split(":")[0]
            port = int(weaviate_url.split(":")[1])
        else:
            host = weaviate_url
            port = 8080
            
        # 注意：connect_to_local 实际上是用于连接自定义的 host/port，不局限于 localhost
        self.client = weaviate.connect_to_local(
            host=host,
            port=port,
            headers={
                "X-OpenAI-Api-Key": settings.VOLC_API_KEY or ""  # 避免 None 报错
            }
        )
        self.collection_name = "KnowledgeChunk"

    def close(self):
        self.client.close()

    def init_schema(self):
        """初始化 Schema."""
        if not self.client.collections.exists(self.collection_name):
            self.client.collections.create(
                name=self.collection_name,
                vectorizer_config=config.Configure.Vectorizer.none(), # 我们自己生成向量
                properties=[
                    config.Property(name="content", data_type=config.DataType.TEXT),
                    config.Property(name="doc_id", data_type=config.DataType.INT),
                    config.Property(name="kb_type", data_type=config.DataType.TEXT),
                    config.Property(name="tags", data_type=config.DataType.TEXT_ARRAY),
                    config.Property(name="source", data_type=config.DataType.TEXT),
                ]
            )
            print(f"Collection {self.collection_name} created.")

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """批量添加切片."""
        collection = self.client.collections.get(self.collection_name)
        
        with collection.batch.dynamic() as batch:
            for chunk in chunks:
                batch.add_object(
                    properties={
                        "content": chunk["content"],
                        "doc_id": chunk["doc_id"],
                        "kb_type": chunk["kb_type"],
                        "tags": chunk["tags"],
                        "source": chunk["source"],
                    },
                    vector=chunk["vector"]
                )
        
        if collection.batch.failed_objects:
            print(f"Failed to add objects: {collection.batch.failed_objects}")
            raise Exception("Failed to add chunks to Weaviate")

    def search(
        self, 
        query_vector: List[float], 
        limit: int = 5,
        filters: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """向量检索."""
        collection = self.client.collections.get(self.collection_name)
        
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=weaviate.classes.query.MetadataQuery(distance=True)
        )
        
        results = []
        for obj in response.objects:
            results.append({
                "content": obj.properties["content"],
                "doc_id": obj.properties["doc_id"],
                "kb_type": obj.properties["kb_type"],
                "source": obj.properties["source"],
                "distance": obj.metadata.distance
            })
            
        return results

    def delete_by_doc_id(self, doc_id: int):
        """删除指定文档的所有切片."""
        collection = self.client.collections.get(self.collection_name)
        collection.data.delete_many(
            where=weaviate.classes.query.Filter.by_property("doc_id").equal(doc_id)
        )

