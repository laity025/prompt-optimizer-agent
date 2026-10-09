# ==========================================================
# 知识库（RAG 检索评测）表模型
# KnowledgeBase：用户的知识库，绑定一批语料文档
# KnowledgeDoc：语料文档（标题 + 全文）
# KnowledgeChunk：文档切分后的块，存储文本与嵌入向量（用于向量/词法检索）
# ==========================================================
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class KnowledgeBase(Base):
    """面向 RAG 检索评测的知识库，供任务/评测绑定。"""

    __tablename__ = "knowledge_bases"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # 嵌入方式：''=本地词法检索（无需外部依赖）；否则为使用的嵌入模型名（向量检索）
    embed_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    doc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    docs = relationship(
        "KnowledgeDoc", back_populates="kb",
        cascade="all, delete-orphan", order_by="KnowledgeDoc.id",
    )
    chunks = relationship(
        "KnowledgeChunk", back_populates="kb",
        cascade="all, delete-orphan",
    )


class KnowledgeDoc(Base):
    """知识库中的一份语料文档。"""

    __tablename__ = "knowledge_docs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # processing / done / failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="done")
    error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    kb = relationship("KnowledgeBase", back_populates="docs")
    chunks = relationship(
        "KnowledgeChunk", back_populates="doc",
        cascade="all, delete-orphan", order_by="KnowledgeChunk.seq",
    )


class KnowledgeChunk(Base):
    """文档切分后的检索单元，text 为切片内容，embedding 存向量或词法指纹。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"), nullable=False)
    doc_id: Mapped[int] = mapped_column(ForeignKey("knowledge_docs.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON 字符串：
    #   embed_model 为空时存 {'ngrams': {词: 频次}} 词法指纹；
    #   使用向量嵌入时存 [float, ...] 向量。
    embedding: Mapped[str] = mapped_column(Text, nullable=True)

    kb = relationship("KnowledgeBase", back_populates="chunks")
    doc = relationship("KnowledgeDoc", back_populates="chunks")