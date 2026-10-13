# chat_db.py
import os
import asyncio
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Text, DateTime
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv
import urllib.parse
from sqlalchemy.dialects.postgresql import UUID

load_dotenv()  

# ==================== SUPABASE CREDENTIALS ====================
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword")
DB_HOST = os.getenv("DB_HOST", "xyzcompany.supabase.co")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

# URL-encode password in case it has special characters
ENCODED_PASSWORD = urllib.parse.quote_plus(DB_PASSWORD)

# Async SQLAlchemy URL
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{ENCODED_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ==================== ASYNC DATABASE SETUP ====================
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# ==================== EXISTING USER TABLE ====================
class User(Base):
    __tablename__ = "users"
   # __table_args__ = {"schema": "public"}
    __table_args__ = {"extend_existing": True}
    user_id = Column(UUID(as_uuid=True), primary_key=True)  # match foreign keys
    username = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    email = Column(String)
    organization = Column(String)
    field_of_study = Column(String)
    phone = Column(String)
    profile_pic = Column(String)
    status = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    public_key = Column(Text, nullable=True)

    chat_members = relationship("ChatMember", back_populates="user")
    messages = relationship("Message", back_populates="sender")
    join_requests = relationship("JoinRequest", back_populates="user")
    created_chats = relationship("Chat", back_populates="creator")


   # public_key = Column(Text, nullable=True)  # <-- New column

# ==================== CHAT TABLES ====================
class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=True)  # group name; nullable for 1:1
    is_group = Column(Boolean, default=False)
    created_by = Column(
        UUID(as_uuid=True), 
        ForeignKey('users.user_id', ondelete='CASCADE'),  # Add FK constraint
        nullable=False,
        index=True
    )

    is_locked = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by], back_populates="created_chats")
    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    join_requests = relationship("JoinRequest", back_populates="chat", cascade="all, delete-orphan")

class ChatMember(Base):
    __tablename__ = "chat_members"
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id",ondelete="CASCADE"), primary_key=True)
    is_admin = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_blocked = Column(Boolean, default=False) 
    last_seen = Column(DateTime)

    chat = relationship("Chat", back_populates="members")
    user = relationship("User", back_populates="chat_members")

class JoinRequest(Base):
    __tablename__ = "join_requests"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id",ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id",ondelete="CASCADE"))
    status = Column(String(20), default="pending")  # pending / accepted / rejected / cancelled
    requested_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="join_requests")
    user = relationship("User", back_populates="join_requests")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id")) # Supabase User UUID
    kind = Column(String(20), default="text")
    ciphertext = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_encrypted = Column(Boolean, default=True)
    iv = Column(Text, nullable=False)  # ✅ ADD THIS
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(100), nullable=True)  # ✅ ADD THIS LINE
    
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    message_keys = relationship("MessageKey", back_populates="message", cascade="all, delete-orphan")


class MessageKey(Base):
    __tablename__ = "message_keys"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id",ondelete="CASCADE"), index=True)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"),index=True)
  # Supabase User UUID
    encrypted_key = Column(Text, nullable=False)

    message = relationship("Message", back_populates="message_keys")


# ==================== DATABASE UTILS ====================
async def init_db():
    async with engine.begin() as conn:
        # Create only the chat-related tables, not users
        await conn.run_sync(Base.metadata.create_all, tables=[
            Chat.__table__,
            ChatMember.__table__,
            JoinRequest.__table__,
            Message.__table__,
            MessageKey.__table__,
            ])

    print("Database tables created!")


# ==================== RUN ====================
if __name__ == "__main__":
    asyncio.run(init_db())
