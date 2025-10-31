# metasimpy/core/cognition/memory.py

import datetime
import math
import uuid
from enum import Enum
from typing import List, Optional, Dict, Tuple
import chromadb
from loguru import logger
from pydantic import BaseModel, Field

from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel
from langchain_core.documents import Document

from metasimpy.core.engine.timeline import Timeline


class MemoryType(str, Enum):
    """定义记忆的类型"""

    OBSERVATION = "观察"
    DIALOGUE = "对话"
    ACTION = "行动"
    REFLECTION = "反思"
    MENTOR_GUIDANCE = "导师建议"
    USER_SPECIFIED = "用户指定"


class MemoryRecord(BaseModel):
    """定义一条记忆记录的数据结构"""

    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一标识符")
    agent_id: str = Field(..., description="拥有该记忆的 Agent ID")
    timestamp: datetime.datetime = Field(..., description="记忆发生的时间戳")
    type: MemoryType = Field(..., description="记忆类型")
    content: str = Field(..., description="记忆的具体文本内容")
    importance: int = Field(default=5, ge=1, le=10, description="记忆的重要性评分 (1-10)")
    related_agent_ids: Optional[List[str]] = Field(default=None, description="与此记忆相关的其他 Agent ID")

    def to_langchain_document(self) -> Document:
        """将 MemoryRecord 转换为 LangChain Document 用于存储"""
        metadata = {
            "agent_id": self.agent_id,
            "timestamp_iso": self.timestamp.isoformat(),
            "timestamp_unix": self.timestamp.timestamp(),
            "type": self.type.value,
            "importance": self.importance,
            "memory_id": self.memory_id,
            "related_agent_ids": ",".join(self.related_agent_ids) if self.related_agent_ids else "",
        }
        return Document(page_content=self.content, metadata=metadata)

    @classmethod
    def from_langchain_document(cls, doc: Document) -> "MemoryRecord":
        """从 LangChain Document 重构 MemoryRecord"""
        related_ids = doc.metadata.get("related_agent_ids")
        return cls(
            memory_id=doc.metadata.get("memory_id", str(uuid.uuid4())),
            agent_id=doc.metadata["agent_id"],
            timestamp=datetime.datetime.fromisoformat(doc.metadata["timestamp_iso"]) if "timestamp_iso" in doc.metadata else datetime.datetime.fromtimestamp(doc.metadata["timestamp_unix"]),
            type=MemoryType(doc.metadata["type"]),
            content=doc.page_content,
            importance=doc.metadata["importance"],
            related_agent_ids=related_ids.split(",") if related_ids else None,
        )


class MemorySystem:
    """封装了 Agent 长期记忆的存储与检索逻辑。使用 ChromaDB 作为向量存储后端，并结合 LangChain 组件"""

    def __init__(
        self,
        embedding_function: Embeddings,
        importance_llm: Optional[BaseLanguageModel] = None,
        chroma_persist_directory: str = "./db/chroma_db",
        recency_decay_factor: float = 0.99,
    ):
        self.embedding_function = embedding_function
        self.importance_llm = importance_llm
        self.persist_directory = chroma_persist_directory
        self.recency_decay_factor = recency_decay_factor

        try:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(f"ChromaDB 持久化客户端已连接到: {self.persist_directory}")
        except Exception as persist_error:
            logger.warning(f"持久化客户端失败 ({persist_error})，尝试使用普通客户端")
            self._client = chromadb.Client()
            logger.info("ChromaDB 普通客户端已连接")

        self._agent_collections: Dict[str, Chroma] = {}

    def _get_or_create_agent_collection(self, agent_id: str) -> Chroma:
        """获取或创建指定 Agent 的 ChromaDB Collection 对应的 LangChain Chroma 对象"""
        if agent_id not in self._agent_collections:
            collection_name = f"agent_{agent_id}_memory"
            logger.debug(f"为 Agent '{agent_id}' 加载或创建 Chroma Collection: {collection_name}")
            self._agent_collections[agent_id] = Chroma(client=self._client, collection_name=collection_name, embedding_function=self.embedding_function, persist_directory=self.persist_directory)  # 确保每次都指向持久化目录
        return self._agent_collections[agent_id]

    async def _calculate_importance(self, content: str) -> int:
        """评估记忆内容的重要性 (1-10)"""
        if not self.importance_llm:
            content_lower = content.lower()
            if "反思" in content or "总结" in content or "insight" in content_lower:
                return 8
            elif "导师建议" in content or "mentor suggests" in content_lower:
                return 10
            elif "说：" in content or "asked:" in content_lower:
                return 6
            elif "看到" in content or "observed:" in content_lower:
                return 4
            else:
                return 5
        else:
            prompt = f"""
            评估以下记忆内容的重要性，范围从 1 (非常不重要) 到 10 (极其重要)。
            考虑其对智能体长期目标、关系或自我认知的潜在影响。
            记忆内容: "{content}"
            请只输出一个 1 到 10 之间的整数。
            重要性评分: """
            try:
                response = await self.importance_llm.ainvoke(prompt)
                score = int(response.strip())
                return max(1, min(10, score))
            except Exception as e:
                logger.warning(f"使用 LLM 评估重要性失败: {e}. 回退到默认值 5。")
                return 5

    async def add_memory(self, agent_id: str, memory_record: MemoryRecord):
        """将一条新的记忆记录添加到指定 Agent 的记忆库中"""
        if not memory_record.content:
            logger.warning("尝试添加内容为空的记忆，已跳过。")
            return

        try:
            chroma_collection = self._get_or_create_agent_collection(agent_id)

            memory_record.importance = await self._calculate_importance(memory_record.content)
            logger.trace(f"Memory importance calculated: {memory_record.importance} for content: '{memory_record.content[:50]}...'")

            doc = memory_record.to_langchain_document()

            memory_ids = [memory_record.memory_id]
            added_ids = await chroma_collection.aadd_documents([doc], ids=memory_ids)

            if added_ids:
                logger.debug(f"Agent '{agent_id}' 添加记忆成功 (ID: {added_ids[0]}), 类型: {memory_record.type.value}, 重要性: {memory_record.importance}")
                # self._client.persist() # 根据需要取消注释，可能会影响性能
            else:
                logger.warning(f"Agent '{agent_id}' 添加记忆失败 (可能已存在或出错): {memory_record.memory_id}")

        except Exception as e:
            logger.error(f"添加记忆失败 (Agent ID: {agent_id}): {e}", exc_info=True)

    def _apply_rri_weighting(self, results_with_scores: List[Tuple[Document, float]], current_time: datetime.datetime) -> List[Tuple[Document, float]]:
        """对 ChromaDB 返回的相似度搜索结果应用 RRI (相关性, 时近性, 重要性) 加权。"""
        weighted_results = []
        now_unix = current_time.timestamp()

        for doc, relevance_score in results_with_scores:
            try:
                importance = doc.metadata.get("importance", 5)
                timestamp_unix = doc.metadata.get("timestamp_unix", now_unix)

                hours_ago = (now_unix - timestamp_unix) / 3600.0
                recency_score = math.pow(self.recency_decay_factor, hours_ago)

                combined_score = relevance_score * (importance / 10.0) * recency_score

                weighted_results.append((doc, combined_score))
                logger.trace(f"RRI Calc for '{doc.page_content[:30]}...': Rel={relevance_score:.2f}, Imp={importance}, Rec={recency_score:.2f} ({(hours_ago):.1f} hrs ago) -> Combined={combined_score:.3f}")

            except Exception as e:
                logger.warning(f"计算 RRI 分数时出错: {e} for doc: {doc.metadata.get('memory_id')}")
                weighted_results.append((doc, relevance_score * 0.1))

        weighted_results.sort(key=lambda x: x[1], reverse=True)

        return weighted_results

    async def retrieve_memories(self, agent_id: str, query_text: str, current_time: datetime.datetime, top_k: int = 10) -> List[MemoryRecord]:
        """指定 Agent 检索最相关的记忆 (按 RRI 加权)。"""
        retrieved_records = []
        try:
            chroma_collection = self._get_or_create_agent_collection(agent_id)
            results_with_scores: List[Tuple[Document, float]] = await chroma_collection.asimilarity_search_with_score(query_text, k=top_k * 2)

            logger.debug(f"Agent '{agent_id}': 初始检索到 {len(results_with_scores)} 条记忆 for query '{query_text[:50]}...'")
            if not results_with_scores:
                return []
            rri_weighted_results = self._apply_rri_weighting(results_with_scores, current_time)
            for doc, score in rri_weighted_results[:top_k]:
                try:
                    record = MemoryRecord.from_langchain_document(doc)
                    retrieved_records.append(record)
                    logger.trace(f"Retrieved memory (RRI Score: {score:.3f}): {record.content[:100]}...")
                except Exception as conversion_error:
                    logger.warning(f"从 Document 转换 MemoryRecord 失败: {conversion_error} for doc: {doc.metadata.get('memory_id')}")

            logger.info(f"Agent '{agent_id}': RRI 检索完成，返回 {len(retrieved_records)} 条记忆。")

        except Exception as e:
            logger.error(f"检索记忆失败 (Agent ID: {agent_id}): {e}", exc_info=True)

        return retrieved_records

    async def get_all_memories_for_agent(self, agent_id: str) -> List[MemoryRecord]:
        """获取指定 Agent 的所有记忆 (主要用于调试)"""
        all_records = []
        try:
            chroma_collection = self._get_or_create_agent_collection(agent_id)
            results = chroma_collection.get(include=["metadatas", "documents"])
            if results and results.get("documents"):
                for i, content in enumerate(results["documents"]):
                    metadata = results["metadatas"][i]
                    doc = Document(page_content=content, metadata=metadata)
                    try:
                        record = MemoryRecord.from_langchain_document(doc)
                        all_records.append(record)
                    except Exception as conversion_error:
                        logger.warning(f"从 Document 转换 MemoryRecord 失败 (get_all): {conversion_error} for doc metadata: {metadata}")
                all_records.sort(key=lambda x: x.timestamp)
        except Exception as e:
            logger.error(f"获取 Agent '{agent_id}' 所有记忆失败: {e}", exc_info=True)
        return all_records
