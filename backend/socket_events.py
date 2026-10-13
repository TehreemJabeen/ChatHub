# socket_events.py - Complete Socket.IO Event Handlers
import socketio
from datetime import datetime
from sqlalchemy import select, delete, desc, func,update,and_
import jwt

from db.database import (
    AsyncSessionLocal, User, Chat, ChatMember,
    Message, JoinRequest, MessageKey
)
from auth_utils2 import get_user_id_from_token
from utils import (
    logger
)
import os
from uuid import UUID

# ============================================================
# SOCKET.IO SERVER
# ✅ Connection Management
# - connect()           # Authenticate & load chats
# - disconnect()        # Clean up sessions

# # ✅ Room/Group Management  
# - create_room()       # Create new chat
# - join_request()      # Request to join locked group
# - process_join_request()  # Admin approve/reject
# - exit_group()        # Leave a group

# # ✅ Chat Operations
# - enter_chat()        # Join room & load messages
# - leave_chat()        # Leave room (but stay member)
# - send_message()      # Send encrypted message
# - load_messages()     # Pagination

# # ✅ Admin Actions
# - admin_remove_member()   # Kick user
# - admin_delete_chat()     # Delete entire chat
# - admin_promote_member()  # Make admin
# - admin_demote_member()   # Remove admin

# # ✅ Utilities
# - get_pending_requests()  # List join requests
# ============================================================

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"

# Rate limiting
# create_room_rate_limit = {}

# Room name validation
MAX_ROOM_NAME_LENGTH = 200
MIN_ROOM_NAME_LENGTH = 1

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
    ping_interval=25,
    ping_timeout=60,
    allow_upgrades=True,
    http_compression=True
)

# ============================================================
# STATE TRACKING
# ============================================================

active_users = {}
active_chats = {}
active_chat_sessions = {}

def get_user_id_by_sid(sid):
    """Get user_id from socket ID"""
    for user_id, sids in active_users.items():
        if sid in sids:
            return user_id
    return None

def get_user_uuid_by_sid(sid):
    """Get user_id as UUID from socket ID"""
    user_id = get_user_id_by_sid(sid)
    if user_id:
        try:
            return UUID(str(user_id))
        except ValueError:
            return None
    return None


async def check_duplicate_group_name(session, name: str, user_id: str) -> bool:
    """Check if user already has a group chat with this exact name"""
    if not name:
        return False
    
    result = await session.execute(
        select(Chat.id)
        .join(ChatMember, Chat.id == ChatMember.chat_id)
        .where(
            Chat.name == name,
            Chat.is_group == True,
            ChatMember.user_id == user_id,
            Chat.is_archived == False
        )
        .limit(1)
    )
    
    return result.first() is not None



@sio.event(namespace="/chat")
async def disconnect(sid):
    """Handle client disconnection"""
    user_id = get_user_id_by_sid(sid)
    
    if user_id:
        print(f"\n🔌 DISCONNECT: User {user_id}, SID {sid}")
        
        if user_id in active_users:
            active_users[user_id].discard(sid)
            
            if not active_users[user_id]:
                del active_users[user_id]
                print(f"   ✅ User {user_id} fully disconnected")
            else:
                print(f"   ℹ️  User {user_id} still has {len(active_users[user_id])} active session(s)")
    else:
        print(f"\n🔌 DISCONNECT: Unknown SID {sid}")

@sio.event(namespace="/chat")
async def create_room(sid, data):
    """Create a new chat room"""
    print("\n" + "="*50)
    print("[CREATE ROOM REQUEST]")
    print("="*50)
    print(f"SID: {sid}")
    print(f"Data: {data}")
    
    # Authenticate user - get as string first
    user_id_str = get_user_id_by_sid(sid)
    
    if not user_id_str:
        print("[ERROR] REJECTED: User not authenticated")
        await sio.emit(
            "create_room_error",
            {"error": "Not authenticated. Please reconnect."},
            to=sid,
            namespace="/chat"
        )
        return
    
    # Convert to UUID for database operations
    try:
        user_id = UUID(str(user_id_str))
    except ValueError:
        print(f"[ERROR] Invalid user_id format: {user_id_str}")
        await sio.emit(
            "create_room_error",
            {"error": "Invalid user ID format"},
            to=sid,
            namespace="/chat"
        )
        return
    
    print(f"[USER] {user_id}")
    
    # Extract input
    room_name = data.get("room_name", "").strip() if data.get("room_name") else None
    is_group = data.get("is_group", False)
    is_locked = data.get("is_locked", False)
    
    print(f"[ROOM] Name: {room_name or '(unnamed)'}")
    print(f"[ROOM] Is group: {is_group}")
    print(f"[ROOM] Is locked: {is_locked}")
    
    # Database operations
    async with AsyncSessionLocal() as session:
        try:
            # Verify user exists (use UUID)
            user_result = await session.execute(
                select(User.username, User.full_name)
                .where(User.user_id == user_id)
            )
            user = user_result.first()
            
            if not user:
                print(f"[ERROR] REJECTED: User {user_id} not found")
                await sio.emit(
                    "create_room_error",
                    {"error": "User account not found"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            print(f"[OK] User verified: {user.username}")
            
            # # Check duplicate name (pass UUID)
            # if is_group and room_name:
            #     has_duplicate = await check_duplicate_group_name(session, room_name, user_id)
            #     if has_duplicate:
            #         print(f"[WARN] REJECTED: Duplicate group name '{room_name}'")
            #         await sio.emit(
            #             "create_room_error",
            #             {"error": f"You already have a group named '{room_name}'"},
            #             to=sid,
            #             namespace="/chat"
            #         )
            #         return
            
            # Create chat - created_by should be string for your schema
            new_chat = Chat(
                name=room_name,
                is_group=is_group,
                is_locked=is_locked,
                created_by=user_id,  #no String for created_by field
                created_at=datetime.utcnow(),
                is_archived=False
            )
            session.add(new_chat)
            await session.flush()
            
            chat_id = new_chat.id
            print(f"[OK] Created chat with ID: {chat_id}")
            
            # Add creator as admin (use UUID for user_id)
            creator_member = ChatMember(
                chat_id=chat_id,
                user_id=user_id,  # UUID object
                is_admin=True,
                is_blocked=False,
                joined_at=datetime.utcnow(),
                last_seen=datetime.utcnow()
            )
            session.add(creator_member)
            
            await session.commit()
            await session.refresh(new_chat)
            
            print(f"[OK] Added {user.username} as admin")
            
            # Update rate limit (use string key for dict)
            # if user_id_str not in create_room_rate_limit:
            #     create_room_rate_limit[user_id_str] = []
            # create_room_rate_limit[user_id_str].append(datetime.utcnow())
            
            # Response data (convert UUID to string for JSON)
            room_data = {
                "chat_id": chat_id,
                "name": room_name,
                "is_group": is_group,
                "is_locked": is_locked,
                "is_admin": True,
                "created_by": str(user_id),
                "created_by_username": user.username,
                "created_by_full_name": user.full_name,
                "created_at": new_chat.created_at.isoformat(),
                "member_count": 1
            }
            
            # Emit success
            await sio.emit(
                "create_room_success",
                {"room": room_data},
                to=sid,
                namespace="/chat"
            )
            
            # Broadcast public groups
            if is_group and not is_locked:
                print(f"[BROADCAST] New public group available")
                
                broadcast_data = {
                    "chat_id": chat_id,
                    "name": room_name,
                    "is_locked": False,
                    "created_by": str(user_id),
                    "created_by_username": user.username,
                    "created_at": new_chat.created_at.isoformat()
                }
                
                await sio.emit(
                    "new_group_available",
                    broadcast_data,
                    namespace="/chat",
                    skip_sid=sid
                )
            
            print("\n" + "="*50)
            print("[OK] ROOM CREATED SUCCESSFULLY")
            print("="*50)
            print(f"Chat ID: {chat_id}")
            print(f"Name: {room_name or 'Direct Message'}")
            print(f"Type: {'Group' if is_group else 'Direct'}")
            print("="*50 + "\n")
            
        except Exception as e:
            await session.rollback()
            print(f"\n[ERROR] creating room:")
            print(f"   User: {user_id}")
            print(f"   Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            await sio.emit(
                "create_room_error",
                {"error": "An error occurred while creating the room."},
                to=sid,
                namespace="/chat"
            )

#=========================JOIN REQUEST=========================
@sio.event(namespace="/chat")
async def join_request(sid, data):
    """
    User requests to join a group chat.
    
    Expected data:
    {
        "chat_id": int
    }
    
    Emits:
        - "join_request_submitted": Success
        - "join_request_error": Error
    """
    print("\n" + "="*50)
    print("[JOIN REQUEST]")
    print("="*50)
    print(f"SID: {sid}")
    print(f"Data: {data}")
    
    chat_id = data.get("chat_id")
    if not chat_id:
        print("[ERROR] REJECTED: No chat_id provided")
        await sio.emit(
            "join_request_error",
            {"error": "chat_id is required"},
            to=sid,
            namespace="/chat"
        )
        return

    # Get user_id as string first
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        print("[ERROR] REJECTED: User not authenticated")
        await sio.emit(
            "join_request_error",
            {"error": "User not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    # Convert to UUID for database operations
    try:
        user_id = UUID(str(user_id_str))
    except ValueError:
        print(f"[ERROR] Invalid user_id format: {user_id_str}")
        await sio.emit(
            "join_request_error",
            {"error": "Invalid user ID format"},
            to=sid,
            namespace="/chat"
        )
        return
    
    print(f"[USER] {user_id}")
    print(f"[CHAT] {chat_id}")

    async with AsyncSessionLocal() as session:
        try:
            # Check if chat exists and is a group
            chat_result = await session.execute(
                select(Chat.id, Chat.name, Chat.is_group, Chat.is_locked, Chat.created_by)
                .where(Chat.id == chat_id)
                .where(Chat.is_archived == False)
            )
            chat = chat_result.first()
            
            if not chat:
                print(f"[ERROR] REJECTED: Chat {chat_id} not found")
                await sio.emit(
                    "join_request_error",
                    {"error": "Chat not found"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            if not chat.is_group:
                print(f"[ERROR] REJECTED: Chat {chat_id} is not a group")
                await sio.emit(
                    "join_request_error",
                    {"error": "Cannot join non-group chats"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            print(f"[OK] Chat found: {chat.name}")
            print(f"     Locked: {chat.is_locked}")
            
            # Check if already a member (use UUID)
            member_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            existing_member = member_result.scalar_one_or_none()

            if existing_member:
                print(f"[ERROR] REJECTED: User already a member")
                await sio.emit(
                    "join_request_error",
                    {"error": "You are already a member of this chat"},
                    to=sid,
                    namespace="/chat"
                )
                return

            # If chat is NOT locked, add user directly
            if not chat.is_locked:
                print(f"[UNLOCKED] Adding user directly")
                
                new_member = ChatMember(
                    chat_id=chat_id,
                    user_id=user_id,  # UUID object
                    is_admin=False,
                    is_blocked=False,
                    joined_at=datetime.utcnow(),
                    last_seen=datetime.utcnow()
                )
                session.add(new_member)
                await session.flush()
                await session.commit()
                                
                # Get user info
                user_result = await session.execute(
                    select(User.username, User.full_name)
                    .where(User.user_id == user_id)
                )
                user_info = user_result.first()
                
                await sio.emit(
                    "join_request_submitted",
                    {
                        "chat_id": chat_id,
                        "chat_name": chat.name,
                        "status": "approved",
                        "message": "You have joined the chat",
                        "auto_approved": True
                    },
                    to=sid,
                    namespace="/chat"
                )
                
                # Notify chat members
                await sio.emit(
                    "user_joined_chat",
                    {
                        "chat_id": chat_id,
                        "user_id": str(user_id),  # Convert back to string for JSON
                        "username": user_info.username if user_info else "Unknown",
                        "joined_at": datetime.utcnow().isoformat()
                    },
                    room=f"chat_{chat_id}",
                    namespace="/chat"
                )
                
                print(f"[OK] User added to unlocked chat")
                return

            # Chat is locked - check for pending request (use UUID)
            pending_result = await session.execute(
                select(JoinRequest)
                .where(JoinRequest.chat_id == chat_id)
                .where(JoinRequest.user_id == user_id)
                .where(JoinRequest.status == "pending")
            )
            pending_req = pending_result.scalar_one_or_none()

            if pending_req:
                print(f"[WARN] REJECTED: Pending request already exists")
                await sio.emit(
                    "join_request_error",
                    {"error": "You already have a pending join request"},
                    to=sid,
                    namespace="/chat"
                )
                return

            # Create new join request for locked chat (use UUID)
            join_req = JoinRequest(
                chat_id=chat_id,
                user_id=user_id,  # UUID object
                status="pending",
                requested_at=datetime.utcnow(),
                processed_at=None
            )
            session.add(join_req)
            await session.commit()
            await session.refresh(join_req)
            
            # Get user info for notification
            user_result = await session.execute(
                select(User.username, User.full_name)
                .where(User.user_id == user_id)
            )
            user_info = user_result.first()

            # Emit success to requester
            await sio.emit(
                "join_request_submitted",
                {
                    "chat_id": chat_id,
                    "chat_name": chat.name,
                    "status": "pending",
                    "request_id": join_req.id,
                    "message": "Join request submitted."
                },
                to=sid,
                namespace="/chat"
            )
            
            # Notify chat admins
            admin_result = await session.execute(
                select(ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.is_admin == True)
            )
            admin_ids = [str(row[0]) for row in admin_result.all()]
            
            # Send notification to all online admins
            for admin_id in admin_ids:
                if admin_id in active_users:
                    sids_copy = list(active_users[admin_id])
                    for admin_sid in sids_copy:
                        await sio.emit(
                            "new_join_request",
                            {
                                "request_id": join_req.id,
                                "chat_id": chat_id,
                                "chat_name": chat.name,
                                "user_id": str(user_id),  # String for JSON
                                "username": user_info.username if user_info else "Unknown",
                                "full_name": user_info.full_name if user_info else None,
                                "requested_at": join_req.requested_at.isoformat()
                            },
                            to=admin_sid,
                            namespace="/chat"
                        )
            
            print("\n" + "="*50)
            print("[OK] JOIN REQUEST SUBMITTED")
            print("="*50)
            print(f"Request ID: {join_req.id}")
            print(f"User: {user_id}")
            print(f"Chat: {chat.name} (ID: {chat_id})")
            print(f"Status: pending")
            print(f"Notified {len(admin_ids)} admin(s)")
            print("="*50 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"\n[ERROR] in join_request:")
            print(f"   User: {user_id}")
            print(f"   Chat: {chat_id}")
            print(f"   Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            await sio.emit(
                "join_request_error",
                {"error": "Failed to submit join request"},
                to=sid,
                namespace="/chat"
            )

# Add these imports at the top of main.py
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import base64
import os


@sio.event( namespace="/chat")
async def enter_chat(sid, data):
    """
    Client enters a chat room and loads messages
    Payload: { chat_id, before_id?, limit? }
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Get user from session - ✅ CONSISTENT with other events
            user_id_str = get_user_id_by_sid(sid)
            if not user_id_str:
                await sio.emit("enter_chat_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
                return
            
            # Convert string to UUID for DB queries
            from uuid import UUID
            try:
                user_id = UUID(user_id_str)
            except ValueError:
                logger.error(f"Invalid UUID: {user_id_str}")
                await sio.emit("enter_chat_error", {"error": "Invalid user ID format"}, to=sid, namespace="/chat")
                return
            
            # 2. Validate input
            chat_id = data.get("chat_id")
            before_id = data.get("before_id")
            limit = data.get("limit", 50)
            
            if not chat_id:
                await sio.emit("enter_chat_error", {"error": "Missing chat_id"}, to=sid, namespace="/chat")
                return
            
            # 3. Check membership and get chat info
            membership_query = (
                select(ChatMember, Chat)
                .join(Chat, ChatMember.chat_id == Chat.id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
                .where(ChatMember.is_blocked == False)
            )
            
            result = await session.execute(membership_query)
            membership_data = result.first()
            
            if not membership_data:
                await sio.emit("enter_chat_error", {"error": "Chat not found or not a member"}, to=sid, namespace="/chat")
                return
            
            membership, chat_info = membership_data
            
            # 4. Join socket room
            room_name = f"chat_{chat_id}"
            await sio.enter_room(sid, room_name, namespace="/chat")
            
            # 5. Track active chat session - Use string for dict keys
            if chat_id not in active_chats:
                active_chats[chat_id] = set()
            active_chats[chat_id].add(user_id_str)
            
            if user_id_str not in active_chat_sessions:
                active_chat_sessions[user_id_str] = {}
            active_chat_sessions[user_id_str][sid] = chat_id
            
            # 6. Update last_seen - Use UUID for DB
            await session.execute(
                ChatMember.__table__.update()
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
                .values(last_seen=datetime.utcnow())
            )
            await session.commit()
            
            # 7. Load messages with proper joins
            msg_query = (
                select(
                    Message.id,
                    Message.sender_id,
                    Message.kind,
                    Message.ciphertext,
                    Message.iv,  # ✅ Added IV field
                    Message.created_at,
                    Message.is_encrypted,
                    Message.file_url,
                    Message.file_name,
                    Message.file_size,
                    Message.file_type,  # ✅ Added file_type field
                    User.username.label("sender_username"),
                    User.full_name.label("sender_full_name")
                )
                .join(User, Message.sender_id == User.user_id)
                .where(Message.chat_id == chat_id)
                .where(Message.created_at >= membership.joined_at)  # ✅ Hide pre-join messages
            )
            
            if before_id:
                msg_query = msg_query.where(Message.id < before_id)
            
            msg_query = msg_query.order_by(desc(Message.created_at)).limit(limit)
            
            msg_result = await session.execute(msg_query)
            messages_raw = msg_result.all()
            
            # 8. Get encrypted keys - Use UUID for DB
            message_ids = [m.id for m in messages_raw]
            keys_map = {}
            
            if message_ids:
                keys_result = await session.execute(
                    select(MessageKey.message_id, MessageKey.encrypted_key)
                    .where(MessageKey.message_id.in_(message_ids))
                    .where(MessageKey.recipient_id == user_id)
                )
                keys_map = {row.message_id: row.encrypted_key for row in keys_result.all()}
            
            # 9. Build message list with all fields
            messages = [
                {
                    "id": m.id,
                    "sender_id": str(m.sender_id),
                    "sender_username": m.sender_username,
                    "sender_full_name": m.sender_full_name,
                    "kind": m.kind,
                    "ciphertext": m.ciphertext,
                    "iv": m.iv,  # ✅ Include IV for decryption
                    "encrypted_key": keys_map.get(m.id),
                    "is_encrypted": m.is_encrypted,
                    "file_url": m.file_url,
                    "file_name": m.file_name,
                    "file_size": m.file_size,
                    "file_type": getattr(m, 'file_type', None),     
                    "created_at": m.created_at.isoformat() + 'Z' if m.created_at else None,               
                    #"created_at": m.created_at.isoformat() if m.created_at else None,
                    "is_own": str(m.sender_id) == user_id_str
                }
                for m in reversed(messages_raw)
            ]
            
            # 10. Get member list with proper joins
            members_result = await session.execute(
                select(
                    ChatMember.user_id,
                    ChatMember.is_admin,
                    User.username,
                    User.full_name,
                    User.public_key
                )
                .join(User, ChatMember.user_id == User.user_id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.is_blocked == False)
            )
            members = [
                {
                    "user_id": str(m.user_id),
                    "username": m.username,
                    "full_name": m.full_name,
                    "is_admin": m.is_admin,
                    "public_key": m.public_key,
                    "is_online": str(m.user_id) in active_users
                }
                for m in members_result.all()
            ]
            
            # 11. Emit success response
            await sio.emit(
                "entered_chat",
                {
                    "chat_id": chat_id,
                    "name": chat_info.name,
                    "is_group": chat_info.is_group,
                    "is_locked": chat_info.is_locked,
                    "is_admin": membership.is_admin,
                    "members": members,
                    "messages": messages,
                    "has_more": len(messages_raw) == limit
                },
                to=sid,
                namespace="/chat"
            )
            
            # 12. Notify others in the chat - Use string
            await sio.emit(
                "user_online",
                {"user_id": user_id_str, "chat_id": chat_id},
                room=room_name,
                skip_sid=sid,
                namespace="/chat"
            )
            
            print(f"✅ User {user_id_str} entered chat {chat_id}, loaded {len(messages)} messages")
            

        except Exception as e:
            print(f"❌ ERROR in enter_chat: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("enter_chat_error", {"error": "Failed to enter chat"}, to=sid, namespace="/chat")
# ============================================================
# ============================================================

@sio.event(namespace="/chat")
async def leave_chat(sid, data):
    """User leaves a chat room"""
    chat_id = data.get("chat_id")
    
    # [ok] FIX: Get both formats
    user_id_str = get_user_id_by_sid(sid)
    
    if not user_id_str or not chat_id:
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        return
    
    room_name = f"chat_{chat_id}"
    await sio.leave_room(sid, room_name, namespace="/chat")
    
    # Clean up tracking - [ok] Use string for dict keys
    if chat_id in active_chats:
        active_chats[chat_id].discard(user_id_str)
        if not active_chats[chat_id]:
            del active_chats[chat_id]
    
    if user_id_str in active_chat_sessions:
        active_chat_sessions[user_id_str].pop(sid, None)
    
    # Update last_seen - [ok] Use UUID for DB
    async with AsyncSessionLocal() as session:
        await session.execute(
            ChatMember.__table__.update()
            .where(ChatMember.chat_id == chat_id)
            .where(ChatMember.user_id == user_id)  # UUID
            .values(last_seen=datetime.utcnow())
        )
        await session.commit()
    
    # Notify others - [ok] Use string in emit
    await sio.emit(
        "user_offline",
        {"user_id": user_id_str, "chat_id": chat_id},
        room=room_name,
        namespace="/chat"
    )
    
    print(f"[BYE] User {user_id_str} left chat {chat_id}")


#======================================================
# EXIT GROUP - Simplified Version
#======================================================

@sio.event(namespace="/chat")
async def exit_group(sid, data):
    """
    Simplified exit group logic:
    - Regular member: Can leave anytime
    - Admin with no other members: Deletes entire chat
    - Admin with other members: Cannot leave (denied)
    
    Expected data:
    {
        "chat_id": int
    }
    """
    print("\n" + "="*50)
    print("🚪 EXIT GROUP (SIMPLIFIED)")
    print("="*50)
    
    chat_id = data.get("chat_id")
    
    if not chat_id:
        await sio.emit(
            "exit_group_error",
            {"error": "chat_id is required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    
    # ✅ FIX: Get user_id as string first
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "exit_group_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    # ✅ FIX: Convert to UUID for database operations
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "exit_group_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    print(f"👤 User: {user_id_str}")
    print(f"💬 Chat: {chat_id}")
    
    

    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Verify chat exists and is a group
            chat = await session.get(Chat, chat_id)
            
            if not chat or chat.is_archived:
                await sio.emit(
                    "exit_group_error",
                    {"error": "Chat not found"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            if not chat.is_group:
                await sio.emit(
                    "exit_group_error",
                    {"error": "Cannot exit non-group chats"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            chat_name = chat.name or "Unnamed Group"
            
            # 2. Check membership
            member_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            member = member_result.scalar_one_or_none()
            
            if not member:
                await sio.emit(
                    "exit_group_error",
                    {"error": "You are not a member of this group"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            is_admin = member.is_admin
            
            # 3. Get user info
            user_result = await session.execute(
                select(User.username, User.full_name)
                .where(User.user_id == user_id)
            )
            user_info = user_result.first()
            username = user_info.username if user_info else "Unknown"
            
            # 4. Count other members (excluding current user)
            other_members_result = await session.execute(
                select(func.count(ChatMember.user_id))
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id != user_id)
            )
            other_members_count = other_members_result.scalar()
            
            print(f"📊 Is Admin: {is_admin}")
            print(f"📊 Other Members: {other_members_count}")
            
            # ===========================================
            # DECISION LOGIC
            # ===========================================
            
            # Case 1: REGULAR MEMBER - Always allowed to leave
            if not is_admin:
                print("✅ Regular member - allowing exit")
                
                # Delete message keys
                await session.execute(
                    delete(MessageKey)
                    .where(
                        MessageKey.recipient_id == user_id,
                        MessageKey.message_id.in_(
                            select(Message.id).where(Message.chat_id == chat_id)
                        )
                    )
                )
                
                # Remove member
                await session.execute(
                    delete(ChatMember)
                    .where(ChatMember.chat_id == chat_id)
                    .where(ChatMember.user_id == user_id)
                )
                
                await session.commit()
                
                # Leave socket room
                room_name = f"chat_{chat_id}"
                await sio.leave_room(sid, room_name, namespace="/chat")
                
                # Clean up tracking
                if chat_id in active_chats:
                    active_chats[chat_id].discard(user_id_str)
                if user_id_str in active_chat_sessions:
                    active_chat_sessions[user_id_str].pop(sid, None)

                
                # Notify user
                await sio.emit(
                    "exit_group_success",
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "message": "You have left the group"
                    },
                    to=sid,
                    namespace="/chat"
                )
                
                # Notify others
                await sio.emit(
                    "member_left",
                    {
                        "chat_id": chat_id,
                        "user_id": user_id_str,
                        "username": username,
                        "timestamp": datetime.utcnow().isoformat() + 'Z'
                    },
                    room=room_name,
                    namespace="/chat"
                )
                
                print(f"✅ Regular member {username} left chat {chat_id}")
                return
            
            # Case 2: ADMIN with NO other members - Delete entire chat
            if is_admin and other_members_count == 0:
                print("🗑️  Admin with no other members - deleting entire chat")
                
                # Get all members for notification (just this user)
                members_result = await session.execute(
                    select(ChatMember.user_id)
                    .where(ChatMember.chat_id == chat_id)
                )
                member_ids = [str(row[0]) for row in members_result.all()]
                
                # Delete all related data
                await session.execute(
                    delete(JoinRequest).where(JoinRequest.chat_id == chat_id)
                )
                
                await session.execute(
                    delete(MessageKey)
                    .where(
                        MessageKey.message_id.in_(
                            select(Message.id).where(Message.chat_id == chat_id)
                        )
                    )
                )
                
                await session.execute(
                    delete(Message).where(Message.chat_id == chat_id)
                )
                
                await session.execute(
                    delete(ChatMember).where(ChatMember.chat_id == chat_id)
                )
                
                await session.delete(chat)
                await session.commit()
                
                # Leave socket room
                room_name = f"chat_{chat_id}"
                await sio.leave_room(sid, room_name, namespace="/chat")
                
                # Clean up tracking
                if chat_id in active_chats:
                    del active_chats[chat_id]
                if user_id_str in active_chat_sessions:
                    active_chat_sessions[user_id_str].pop(sid, None)
                
                # Notify user
                await sio.emit(
                    "chat_deleted",
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "message": "Chat deleted successfully",
                        "reason": "Last member left",
                        "timestamp": datetime.utcnow().isoformat() + 'Z'
                    },
                    to=sid,
                    namespace="/chat"
                )
                
                print(f"✅ Chat {chat_id} deleted (last member left)")
                return
            
            # Case 3: ADMIN with other members - DENY
            if is_admin and other_members_count > 0:
                print(f"❌ Admin with {other_members_count} other members - denying exit")
                
                await sio.emit(
                    "exit_group_error",
                    {
                        "error": f"Cannot leave: You are an admin and {other_members_count} member(s) remain. Please transfer admin role or remove members first.",
                        "other_members_count": other_members_count
                    },
                    to=sid,
                    namespace="/chat"
                )
                return
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            await sio.emit(
                "exit_group_error",
                {"error": "Failed to exit group"},
                to=sid,
                namespace="/chat"
            )

#======================================================
# ADMIN EVENTS - Member Management
#======================================================
#=========================PROCESS JOIN REQUEST====================
@sio.event(namespace="/chat")
async def get_pending_requests(sid, data):
    """Admin fetches pending join requests"""
    print("\n" + "="*50)
    print("📋 GET PENDING REQUESTS")
    print("="*50)
    
    chat_id = data.get("chat_id")
    if not chat_id:
        await sio.emit("pending_requests_error", {"error": "chat_id is required"}, to=sid, namespace="/chat")
        return
    
    # ✅ Get user_id as string first
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit("pending_requests_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    # ✅ Convert to UUID for database operations
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit("pending_requests_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
        return
    
    print(f"👤 User: {user_id_str}")
    print(f"💬 Chat: {chat_id}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify admin - ✅ Use UUID
            admin_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)  # UUID
                .where(ChatMember.is_admin == True)
            )
            admin_member = admin_result.scalar_one_or_none()
            
            if not admin_member:
                await sio.emit("pending_requests_error", {"error": "You are not an admin of this chat"}, to=sid, namespace="/chat")
                return
            
            # Fetch pending requests
            result = await session.execute(
                select(
                    JoinRequest.id,
                    JoinRequest.user_id,
                    JoinRequest.status,
                    JoinRequest.requested_at,
                    User.username,
                    User.full_name
                )
                .join(User, JoinRequest.user_id == User.user_id)
                .where(JoinRequest.chat_id == chat_id)
                .where(JoinRequest.status == "pending")
                .order_by(JoinRequest.requested_at.asc())
            )
            pending = result.all()
            
            requests = [
                {
                    "request_id": r.id,
                    "user_id": str(r.user_id),  # ✅ Convert UUID to string
                    "username": r.username,
                    "full_name": r.full_name,
                    "status": r.status,
                    "requested_at": r.requested_at.isoformat() if r.requested_at else None
                }
                for r in pending
            ]
            
            print(f"✅ Found {len(requests)} pending requests")
            
            await sio.emit(
                "pending_requests",
                {
                    "chat_id": chat_id,
                    "requests": requests,
                    "count": len(requests)
                },
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("pending_requests_error", {"error": "Failed to fetch pending requests"}, to=sid, namespace="/chat")


@sio.event(namespace="/chat")
async def process_join_request(sid, data):
    """Admin approves or rejects a join request"""
    print("\n" + "="*50)
    print("⚙️  PROCESS JOIN REQUEST")
    print("="*50)
    
    request_id = data.get("request_id")
    action = data.get("action", "").lower()
    
    if not request_id:
        await sio.emit("process_request_error", {"error": "request_id is required"}, to=sid, namespace="/chat")
        return
    
    if action not in ["approve", "reject"]:
        await sio.emit("process_request_error", {"error": "action must be 'approve' or 'reject'"}, to=sid, namespace="/chat")
        return
    
    # ✅ Get user_id as string first
    admin_id_str = get_user_id_by_sid(sid)
    if not admin_id_str:
        await sio.emit("process_request_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    # ✅ Convert to UUID for database operations
    try:
        admin_id = UUID(admin_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {admin_id_str}")
        await sio.emit("process_request_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
        return
    
    print(f"👤 Admin: {admin_id_str}")
    print(f"📝 Request ID: {request_id}")
    print(f"🎯 Action: {action}")
    
    status = "approved" if action == "approve" else "rejected"
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Get the join request
            join_req = await session.get(JoinRequest, request_id)
            
            if not join_req:
                await sio.emit("process_request_error", {"error": "Join request not found"}, to=sid, namespace="/chat")
                return
            
            if join_req.status != "pending":
                await sio.emit("process_request_error", {"error": f"Request already {join_req.status}"}, to=sid, namespace="/chat")
                return
            
            chat_id = join_req.chat_id
            requester_id = join_req.user_id  # ✅ This is UUID from DB
            
            # 2. Verify admin permission - ✅ Use UUID
            admin_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == admin_id)  # UUID
                .where(ChatMember.is_admin == True)
            )
            admin_member = admin_result.scalar_one_or_none()
            
            if not admin_member:
                await sio.emit("process_request_error", {"error": "You are not an admin of this chat"}, to=sid, namespace="/chat")
                return
            
            # 3. Get chat info
            chat_result = await session.execute(
                select(Chat.name).where(Chat.id == chat_id)
            )
            chat_name = chat_result.scalar_one_or_none() or "Unknown"
            
            # 4. Get requester info - ✅ requester_id is already UUID
            user_result = await session.execute(
                select(User.username, User.full_name)
                .where(User.user_id == requester_id)  # UUID
            )
            user_info = user_result.first()
            requester_username = user_info.username if user_info else "Unknown"
            requester_full_name = user_info.full_name if user_info else "Unknown"
            
            # 5. Update join request status
            join_req.status = status
            join_req.processed_at = datetime.utcnow()
            
            # 6. If approved, add user to chat
            if status == "approved":
                # Check not already a member - ✅ Use UUID
                existing = await session.execute(
                    select(ChatMember)
                    .where(ChatMember.chat_id == chat_id)
                    .where(ChatMember.user_id == requester_id)  # UUID
                )
                if not existing.scalar_one_or_none():
                    new_member = ChatMember(
                        chat_id=chat_id,
                        user_id=requester_id,  # ✅ UUID
                        is_admin=False,
                        is_blocked=False,
                        joined_at=datetime.utcnow(),
                        last_seen=datetime.utcnow()
                    )
                    session.add(new_member)
                    print(f"✅ Added {requester_username} to chat")
                else:
                    print(f"⚠️  User {requester_username} already a member")
            
            await session.commit()
            
            # 7. Emit success to admin
            await sio.emit(
                "request_processed",
                {
                    "request_id": request_id,
                    "chat_id": chat_id,
                    "user_id": str(requester_id),  # ✅ Convert UUID to string
                    "username": requester_username,
                    "action": action,
                    "status": status
                },
                to=sid,
                namespace="/chat"
            )
            
            # 8. Notify the requester - ✅ Convert UUID to string for lookup
            requester_id_str = str(requester_id)
            if requester_id_str in active_users:
                event = "join_request_approved" if status == "approved" else "join_request_rejected"
                sids_copy = list(active_users[requester_id_str])
                
                notification_data = {
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "status": status,
                    "message": f"Your join request was {status}"
                }
    
                for req_sid in sids_copy:
                    try:
                        await sio.emit(
                            event,
                            notification_data,
                            to=req_sid,
                            namespace="/chat"
                        )
                    except Exception as emit_error:
                        logger.error(f"Failed to notify requester SID {req_sid}: {emit_error}")
                        
                print(f"📢 Notified requester: {event}")
            else:
                print(f"⚠️  Requester {requester_username} not online")
            
            # 9. If approved, notify chat room members
            if status == "approved":
                await sio.emit(
                    "user_joined_chat",
                    {
                        "chat_id": chat_id,
                        "user_id": requester_id_str,  # ✅ String
                        "username": requester_username,
                        "full_name": requester_full_name,
                        "joined_at": datetime.utcnow().isoformat() + 'Z'
                    },
                    room=f"chat_{chat_id}",
                    namespace="/chat"
                )
                print(f"📢 Notified chat room about new member")
            
            print(f"✅ REQUEST {status.upper()}")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("process_request_error", {"error": "Failed to process request"}, to=sid, namespace="/chat")


# ============================================================
# ADMIN_REMOVE_MEMBER - ⚠️ NEEDS FIXES
# ============================================================
@sio.event(namespace="/chat")
async def admin_remove_member(sid, data):
    """Admin removes a member from chat"""
    print("\n" + "="*50)
    print("🗑️  ADMIN: REMOVE MEMBER")
    print("="*50)
    
    chat_id = data.get("chat_id")
    member_id_str = data.get("member_id")
    
    admin_id_str = get_user_id_by_sid(sid)
    if not admin_id_str:
        await sio.emit("admin_action_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    try:
        admin_id = UUID(admin_id_str)
        member_id = UUID(member_id_str)
    except ValueError as e:
        logger.error(f"Invalid UUID: {e}")
        await sio.emit("admin_action_error", {"error": "Invalid user ID format"}, to=sid, namespace="/chat")
        return
    
    print(f"👤 Admin: {admin_id_str}")
    print(f"💬 Chat: {chat_id}")
    print(f"🎯 Removing: {member_id_str}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify admin permissions
            admin_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == admin_id)
                .where(ChatMember.is_admin == True)
            )
            admin_member = admin_result.scalar_one_or_none()
            
            if not admin_member:
                await sio.emit("admin_action_error", {"error": "You are not an admin of this chat"}, to=sid, namespace="/chat")
                return
            
            # Prevent self-removal
            if member_id_str == admin_id_str:
                await sio.emit("admin_action_error", {"error": "Cannot remove yourself"}, to=sid, namespace="/chat")
                return
            
            # Get member info
            member_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == member_id)
            )
            target_member = member_result.scalar_one_or_none()
            
            if not target_member:
                await sio.emit("admin_action_error", {"error": "Member not found in chat"}, to=sid, namespace="/chat")
                return
            
            # Get username
            user_result = await session.execute(
                select(User.username)
                .where(User.user_id == member_id)
            )
            username = user_result.scalar_one_or_none() or "Unknown"
            
            # Delete message keys
            await session.execute(
                delete(MessageKey)
                .where(
                    MessageKey.recipient_id == member_id,
                    MessageKey.message_id.in_(
                        select(Message.id).where(Message.chat_id == chat_id)
                    )
                )
            )

            # Delete member
            await session.execute(
                delete(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == member_id)
            )
            
            await session.commit()
            
            print(f"✅ Member {username} removed from chat {chat_id}")
            
            # Notify removed user (if online)
            if member_id_str in active_users:
                sids_copy = list(active_users[member_id_str])
                for user_sid in sids_copy:
                    await sio.leave_room(user_sid, f"chat_{chat_id}", namespace="/chat")
                    
                    await sio.emit(
                        "removed_from_chat",
                        {
                            "chat_id": chat_id,
                            "removed_by": admin_id_str,
                            "message": "You have been removed from the chat by admin",
                            "timestamp": datetime.utcnow().isoformat() + 'Z'
                        },
                        to=user_sid,
                        namespace="/chat"
                    )
                print(f"📢 Notified removed user")
            
            # Notify chat members
            await sio.emit(
                "member_removed",
                {
                    "chat_id": chat_id,
                    "removed_user_id": member_id_str,
                    "removed_username": username,
                    "removed_by": admin_id_str,
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                },
                room=f"chat_{chat_id}",
                namespace="/chat"
            )
            
            # Confirm to admin
            await sio.emit(
                "member_removed_success",
                {
                    "chat_id": chat_id,
                    "removed_member": {
                        "user_id": member_id_str,
                        "username": username
                    }
                },
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("admin_action_error", {"error": "Failed to remove member"}, to=sid, namespace="/chat")


@sio.event(namespace="/chat")
async def admin_delete_chat(sid, data):
    """Admin permanently deletes a chat"""
    print("\n" + "="*50)
    print("🗑️  ADMIN: DELETE CHAT")
    print("="*50)
    
    chat_id = data.get("chat_id")
    
    admin_id_str = get_user_id_by_sid(sid)
    if not admin_id_str:
        await sio.emit("admin_action_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    try:
        admin_id = UUID(admin_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {admin_id_str}")
        await sio.emit("admin_action_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
        return
    
    print(f"👤 Admin: {admin_id_str}")
    print(f"💬 Chat: {chat_id}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify admin permissions
            admin_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == admin_id)
                .where(ChatMember.is_admin == True)
            )
            admin_member = admin_result.scalar_one_or_none()
            
            if not admin_member:
                await sio.emit("admin_action_error", {"error": "You are not an admin of this chat"}, to=sid, namespace="/chat")
                return
            
            # Get chat info
            chat = await session.get(Chat, chat_id)
            if not chat:
                await sio.emit("admin_action_error", {"error": "Chat not found"}, to=sid, namespace="/chat")
                return
            
            chat_name = chat.name or "Unnamed Chat"
            
            # Get all members for notification
            members_result = await session.execute(
                select(ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
            )
            member_ids = [str(row[0]) for row in members_result.all()]
            
            print(f"📊 Chat: {chat_name}")
            print(f"👥 Members: {len(member_ids)}")
            
            # Delete all related data (in correct order to respect FK constraints)
            await session.execute(
                delete(JoinRequest).where(JoinRequest.chat_id == chat_id)
            )
            
            await session.execute(
                delete(MessageKey)
                .where(
                    MessageKey.message_id.in_(
                        select(Message.id).where(Message.chat_id == chat_id)
                    )
                )
            )
            
            await session.execute(
                delete(Message).where(Message.chat_id == chat_id)
            )
            
            await session.execute(
                delete(ChatMember).where(ChatMember.chat_id == chat_id)
            )
            
            await session.delete(chat)
            await session.commit()
            print(f"✅ Chat {chat_id} deleted from database")
            
            # Notify ALL members (if online)
            notification_data = {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "deleted_by": admin_id_str,
                "message": f"Chat '{chat_name}' has been deleted by admin",
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
            
            for member_id_str in member_ids:
                if member_id_str in active_users:
                    sids_copy = list(active_users[member_id_str])
                    for user_sid in sids_copy:
                        await sio.leave_room(user_sid, f"chat_{chat_id}", namespace="/chat")
                        
                        await sio.emit(
                            "chat_deleted",
                            notification_data,
                            to=user_sid,
                            namespace="/chat"
                        )
            
            print(f"📢 Notified {len(member_ids)} member(s)")
            
            # Clean up tracking
            if chat_id in active_chats:
                del active_chats[chat_id]
            
            # Confirm to admin
            await sio.emit(
                "chat_deleted_success",
                {
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "message": "Chat deleted successfully"
                },
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("admin_action_error", {"error": "Failed to delete chat"}, to=sid, namespace="/chat")


@sio.event(namespace="/chat")
async def admin_promote_member(sid, data):
    """Admin promotes a member to admin"""
    print("\n" + "="*50)
    print("⬆️  ADMIN: PROMOTE MEMBER")
    print("="*50)
    
    chat_id = data.get("chat_id")
    member_id_str = data.get("member_id")
    
    admin_id_str = get_user_id_by_sid(sid)
    if not admin_id_str:
        await sio.emit("admin_action_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    try:
        admin_id = UUID(admin_id_str)
        member_id = UUID(member_id_str)
    except ValueError:
        logger.error(f"Invalid UUID")
        await sio.emit("admin_action_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify admin permissions
            admin_check = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == admin_id)
                .where(ChatMember.is_admin == True)
            )
            if not admin_check.scalar_one_or_none():
                await sio.emit("admin_action_error", {"error": "You are not an admin"}, to=sid, namespace="/chat")
                return
            
            # Get target member
            member_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == member_id)
            )
            target_member = member_result.scalar_one_or_none()
            
            if not target_member:
                await sio.emit("admin_action_error", {"error": "Member not found"}, to=sid, namespace="/chat")
                return
            
            if target_member.is_admin:
                await sio.emit("admin_action_error", {"error": "User is already an admin"}, to=sid, namespace="/chat")
                return
            
            # Get username
            user_result = await session.execute(
                select(User.username)
                .where(User.user_id == member_id)
            )
            username = user_result.scalar_one_or_none() or "Unknown"
            
            # Promote
            target_member.is_admin = True
            await session.commit()
            
            print(f"✅ Promoted {username} to admin")
            
            # Notify everyone
            await sio.emit(
                "member_promoted",
                {
                    "chat_id": chat_id,
                    "user_id": member_id_str,
                    "username": username,
                    "promoted_by": admin_id_str,
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                },
                room=f"chat_{chat_id}",
                namespace="/chat"
            )
            
            # Confirm to admin
            await sio.emit(
                "member_promoted_success",
                {
                    "chat_id": chat_id,
                    "promoted_member": {
                        "user_id": member_id_str,
                        "username": username
                    }
                },
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("admin_action_error", {"error": "Failed to promote member"}, to=sid, namespace="/chat")


@sio.event(namespace="/chat")
async def admin_demote_member(sid, data):
    """Admin demotes an admin to regular member"""
    print("\n" + "="*50)
    print("⬇️  ADMIN: DEMOTE ADMIN")
    print("="*50)
    
    chat_id = data.get("chat_id")
    member_id_str = data.get("member_id")  # ✅ String from client
    
    # ✅ FIX: Get both formats
    admin_id_str = get_user_id_by_sid(sid)
    if not admin_id_str:
        await sio.emit("admin_action_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
        return
    
    try:
        admin_id = UUID(admin_id_str)
        member_id = UUID(member_id_str)
    except ValueError:
        logger.error(f"Invalid UUID")
        await sio.emit("admin_action_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
        return
    
    # Prevent self-demotion - ✅ Compare strings
    if member_id_str == admin_id_str:
        await sio.emit("admin_action_error", {"error": "Cannot demote yourself"}, to=sid, namespace="/chat")
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify admin permissions - ✅ Use UUID
            admin_check = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == admin_id)  # UUID
                .where(ChatMember.is_admin == True)
            )
            if not admin_check.scalar_one_or_none():
                await sio.emit("admin_action_error", {"error": "You are not an admin"}, to=sid, namespace="/chat")
                return
            
            # Check there's more than 1 admin
            admin_count = await session.execute(
                select(func.count(ChatMember.user_id))
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.is_admin == True)
            )
            if admin_count.scalar() <= 1:
                await sio.emit("admin_action_error", {"error": "Cannot demote the last admin"}, to=sid, namespace="/chat")
                return
            
            # Get target member - ✅ Use UUID
            member_result = await session.execute(
                select(ChatMember)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == member_id)  # UUID
            )
            target_member = member_result.scalar_one_or_none()
            
            if not target_member:
                await sio.emit("admin_action_error", {"error": "Member not found"}, to=sid, namespace="/chat")
                return
            
            if not target_member.is_admin:
                await sio.emit("admin_action_error", {"error": "User is not an admin"}, to=sid, namespace="/chat")
                return
            
            # Get username - ✅ Use UUID
            user_result = await session.execute(
                select(User.username)
                .where(User.user_id == member_id)  # UUID
            )
            username = user_result.scalar_one_or_none() or "Unknown"
            
            # Demote
            target_member.is_admin = False
            await session.commit()
            
            print(f"✅ Demoted {username}")
            
            # Notify everyone - ✅ Use strings
            await sio.emit(
                "member_demoted",
                {
                    "chat_id": chat_id,
                    "user_id": member_id_str,  # String
                    "username": username,
                    "demoted_by": admin_id_str,  # String
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                },
                room=f"chat_{chat_id}",
                namespace="/chat"
            )
            
            # Confirm to admin
            await sio.emit(
                "member_demoted_success",
                {
                    "chat_id": chat_id,
                    "demoted_member": {
                        "user_id": member_id_str,  # String
                        "username": username
                    }
                },
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit("admin_action_error", {"error": "Failed to demote admin"}, to=sid, namespace="/chat")
## 🎯 **Changes Made:**


# ============================================================
@sio.event(namespace="/chat")
async def connect(sid, environ, auth):
    """Handle client connection with authentication"""
    print("\n" + "="*50)
    print("🔌 NEW CONNECTION ATTEMPT")
    print("="*50)
    print(f"SID: {sid}")
    
    # Validate token
    token = auth.get("token") if auth else None
    if not token:
        print("❌ REJECTED: No authentication token provided")
        return False
    
    print(f"Token received: {token[:50]}...")
    
    # Decode and validate JWT
    try:
        user_id = get_user_id_from_token(token)
        print(f"✅ Token valid for user_id: {user_id}")
    except jwt.ExpiredSignatureError:
        print("❌ REJECTED: Token expired")
        return False
    except jwt.InvalidTokenError as e:
        print(f"❌ REJECTED: Invalid token - {e}")
        return False
    except Exception as e:
        print(f"❌ REJECTED: Token validation error - {e}")
        import traceback
        traceback.print_exc()
        return False

    # Register socket ID
    if user_id not in active_users:
        active_users[user_id] = set()
    active_users[user_id].add(sid)
    print(f"📝 Registered SID {sid} for user {user_id}")
    print(f"   Total active sessions: {len(active_users[user_id])}")

    # Database operations
    async with AsyncSessionLocal() as session:
        try:
            # Verify user exists and get public key + username
            user_result = await session.execute(
                select(User.public_key, User.username)
                .where(User.user_id == user_id)
            )
            user_row = user_result.first()
            
            if user_row is None:
                print(f"❌ REJECTED: User {user_id} not found in database")
                active_users[user_id].discard(sid)
                if not active_users[user_id]:
                    del active_users[user_id]
                return False

            current_username = user_row.username
            print(f"✅ User found: {current_username}")
            
            # Check if user needs to upload public key
            needs_public_key = not user_row.public_key
            
            if needs_public_key:
                print(f"⚠️ User {user_id} needs to upload public key")
                await sio.emit(
                    "public_key_required",
                    {
                        "message": "Please generate and upload your public key",
                        "user_id": user_id
                    },
                    to=sid,
                    namespace="/chat"
                )

            # Fetch member chats
            print(f"\n📚 Fetching chat memberships...")
            result = await session.execute(
                select(
                    Chat.id, 
                    Chat.name, 
                    Chat.is_group, 
                    Chat.is_locked, 
                    ChatMember.is_admin
                )
                .join(ChatMember, Chat.id == ChatMember.chat_id)
                .where(ChatMember.user_id == user_id)
                .where(Chat.is_archived == False)
                .order_by(Chat.created_at.desc())
            )
            member_chats = result.all()

            member_chat_list = []
            for c in member_chats:
                chat_id, chat_name, is_group, is_locked, is_admin = c
                
                # For DMs, extract partner's username from stored name
                display_name = chat_name
                if not is_group and chat_name:
                    # Chat name format: "username1|username2"
                    usernames = chat_name.split("|")
                    if len(usernames) == 2:
                        # Show the OTHER user's username
                        display_name = usernames[1] if usernames[0] == current_username else usernames[0]
                
                member_chat_list.append({
                    "chat_id": chat_id,
                    "name": display_name,
                    "is_group": is_group,
                    "is_locked": is_locked,
                    "is_admin": is_admin
                })

            member_chat_ids = [c[0] for c in member_chats]

            # Fetch available group chats
            print(f"🔍 Fetching available group chats...")
            query = select(
                Chat.id, 
                Chat.name, 
                Chat.is_locked, 
                Chat.created_by
            ).where(
                Chat.is_group == True,
                Chat.is_archived == False
            )
            
            if member_chat_ids:
                query = query.where(Chat.id.notin_(member_chat_ids))
            
            query = query.order_by(Chat.created_at.desc())
            
            result = await session.execute(query)
            available_chats = result.all()

            available_chat_list = [
                {
                    "chat_id": c[0],
                    "name": c[1],
                    "is_locked": c[2],
                    "created_by": str(c[3])
                }
                for c in available_chats
            ]

            # Emit chat lists
            await sio.emit(
                "load_chats", 
                {
                    "member_chats": member_chat_list,
                    "available_chats": available_chat_list,
                    "needs_public_key": needs_public_key
                }, 
                to=sid, 
                namespace="/chat"
            )
            
            # Success summary
            print("\n" + "="*50)
            print("✅ CONNECTION SUCCESSFUL")
            print("="*50)
            print(f"User ID: {user_id}")
            print(f"Member of {len(member_chat_list)} chats")
            print(f"Can discover {len(available_chat_list)} available chats")
            print(f"Public key present: {not needs_public_key}")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"\n❌ DATABASE ERROR during connection:")
            print(f"   User: {user_id}")
            print(f"   Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            if user_id in active_users:
                active_users[user_id].discard(sid)
                if not active_users[user_id]:
                    del active_users[user_id]
            
            return False

# ============================================================
# NEW: Upload Public Key Endpoint
# ============================================================
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

def validate_public_key(public_key_pem: str) -> bool:
    """
    Validate that the uploaded key is a valid RSA public key
    
    Args:
        public_key_pem: PEM-formatted public key string
        
    Returns:
        bool: True if valid RSA public key, False otherwise
    """
    try:
        # Try to load the public key
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        
        # Verify it's an RSA key
        if not isinstance(public_key, rsa.RSAPublicKey):
            return False
        
        # Verify key size is at least 2048 bits (security requirement)
        key_size = public_key.key_size
        if key_size < 2048:
            return False
        
        return True
        
    except Exception as e:
        print(f"Invalid public key: {e}")
        return False


# Updated upload_public_key with validation
@sio.event(namespace="/chat")
async def upload_public_key(sid, data):
    """Client uploads their public key (generated on client side)"""
    print("\n" + "="*50)
    print("🔑 UPLOAD PUBLIC KEY")
    print("="*50)
    
    public_key_pem = data.get("public_key")
    
    if not public_key_pem:
        await sio.emit(
            "upload_public_key_error",
            {"error": "public_key required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    # ✅ VALIDATE PUBLIC KEY FORMAT
    # if not validate_public_key(public_key_pem):
    #     await sio.emit(
    #         "upload_public_key_error",
    #         {"error": "Invalid public key format. Must be RSA 2048+ bits in PEM format."},
    #         to=sid,
    #         namespace="/chat"
    #     )
    #     return
    
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "upload_public_key_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "upload_public_key_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Update user's public key
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(public_key=public_key_pem)
            )
            await session.commit()
            
            print(f"✅ Public key saved for user {user_id}")
            print(f"   Key size: {len(public_key_pem)} bytes")
            
            await sio.emit(
                "public_key_uploaded",
                {"success": True, "message": "Public key uploaded successfully"},
                to=sid,
                namespace="/chat"
            )
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit(
                "upload_public_key_error",
                {"error": "Failed to save public key"},
                to=sid,
                namespace="/chat"
            )


@sio.event(namespace="/chat")
async def get_chat_public_keys(sid, data):
    """Get public keys for all members of a chat"""
    chat_id = data.get("chat_id")
    
    if not chat_id:
        await sio.emit(
            "get_public_keys_error",
            {"error": "chat_id required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "get_public_keys_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "get_public_keys_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify user is member
            member_check = await session.execute(
                select(ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            if not member_check.scalar_one_or_none():
                await sio.emit(
                    "get_public_keys_error",
                    {"error": "Not a member of this chat"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            # Get public keys for all members
            result = await session.execute(
                select(User.user_id, User.public_key)
                .join(ChatMember, User.user_id == ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.is_blocked == False)
            )
            
            members = result.all()
            
            public_keys = {
                str(member.user_id): member.public_key
                for member in members
                if member.public_key  # Only include users with keys
            }
            
            await sio.emit(
                "chat_public_keys",
                {
                    "chat_id": chat_id,
                    "public_keys": public_keys
                },
                to=sid,
                namespace="/chat"
            )
            
            print(f"✅ Sent {len(public_keys)} public keys for chat {chat_id}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit(
                "get_public_keys_error",
                {"error": "Failed to get public keys"},
                to=sid,
                namespace="/chat"
            )


# ============================================================
# UPDATED: Send Message (with IV field)
# ============================================================

@sio.event(namespace="/chat")
async def send_message(sid, data):
    """Send E2E encrypted message"""
    print("\n" + "="*50)
    print("📨 SEND MESSAGE")
    print("="*50)
    
    chat_id = data.get("chat_id")
    ciphertext = data.get("ciphertext")
    iv = data.get("iv")  # NEW: Required for AES-GCM
    encrypted_keys = data.get("encrypted_keys", {})
    kind = data.get("kind", "text")
    
    # Validate
    if kind not in ["text", "file", "image"]:
        await sio.emit(
            "send_message_error",
            {"error": "Invalid message kind"},
            to=sid,
            namespace="/chat"
        )
        return
    
    if kind in ["file", "image"]:
        if not data.get("file_url"):
            await sio.emit(
                "send_message_error",
                {"error": "File messages require file_url"},
                to=sid,
                namespace="/chat"
            )
            return
    
    if not chat_id or not ciphertext or not iv:
        await sio.emit(
            "send_message_error",
            {"error": "chat_id, ciphertext, and iv required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "send_message_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "send_message_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    print(f"👤 Sender: {user_id_str}")
    print(f"💬 Chat: {chat_id}")
    print(f"📝 Kind: {kind}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Verify sender is member
            member_result = await session.execute(
                select(ChatMember.is_blocked)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            membership = member_result.scalar_one_or_none()
            
            if membership is None:
                await sio.emit(
                    "send_message_error",
                    {"error": "Not a member"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            if membership:
                await sio.emit(
                    "send_message_error",
                    {"error": "You are blocked"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            # Get sender info
            sender_result = await session.execute(
                select(User.username, User.full_name)
                .where(User.user_id == user_id)
            )
            sender = sender_result.first()
            
            # Create message with IV
            new_message = Message(
                chat_id=chat_id,
                sender_id=user_id,
                kind=kind,
                ciphertext=ciphertext,
                iv=iv,  # NEW: Store IV
                is_encrypted=True,
                created_at=datetime.utcnow(),
                file_url=data.get("file_url"),
                file_name=data.get("file_name"),
                file_size=data.get("file_size"),
                file_type=data.get("file_type")
            )
            session.add(new_message)
            await session.flush()
            
            message_id = new_message.id
            created_at = new_message.created_at
            
            # Store encrypted keys
            for recipient_id_str, enc_key in encrypted_keys.items():
                try:
                    recipient_uuid = UUID(recipient_id_str)
                    msg_key = MessageKey(
                        message_id=message_id,
                        recipient_id=recipient_uuid,
                        encrypted_key=enc_key
                    )
                    session.add(msg_key)
                except ValueError:
                    logger.error(f"Invalid recipient UUID: {recipient_id_str}")
                    continue
            
            await session.commit()
            
            print(f"✅ Message {message_id} saved with {len(encrypted_keys)} keys")
            
            # Broadcast message
            message_data = {
                "id": message_id,
                "chat_id": chat_id,
                "sender_id": user_id_str,
                "sender_username": sender.username if sender else "Unknown",
                "sender_full_name": sender.full_name if sender else None,
                "kind": kind,
                "ciphertext": ciphertext,
                "iv": iv,  # NEW: Include IV
                "is_encrypted": True,
                "file_url": data.get("file_url"),
                "file_name": data.get("file_name"),
                "file_size": data.get("file_size"),
                "file_type": data.get("file_type"),
                "created_at": created_at.isoformat() + 'Z'
            }
            
            # Get all members
            members_result = await session.execute(
                select(ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.is_blocked == False)
            )
            member_ids = [str(row[0]) for row in members_result.all()]
            
            for member_id_str in member_ids:
                if member_id_str in active_users:
                    member_msg = message_data.copy()
                    member_msg["encrypted_key"] = encrypted_keys.get(member_id_str)
                    member_msg["is_own"] = member_id_str == user_id_str
                    
                    sids_copy = list(active_users[member_id_str])
                    
                    for member_sid in sids_copy:
                        try:
                            await sio.emit(
                                "new_message",
                                member_msg,
                                to=member_sid,
                                namespace="/chat"
                            )
                        except Exception as e:
                            logger.error(f"Failed to emit to {member_sid}: {e}")
            
            # Confirm to sender
            await sio.emit(
                "message_sent",
                {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "created_at": created_at.isoformat() + 'Z'
                },
                to=sid,
                namespace="/chat"
            )
            
            print(f"✅ Message broadcast to {len(member_ids)} members")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit(
                "send_message_error",
                {"error": "Failed to send message"},
                to=sid,
                namespace="/chat"
            )
@sio.event(namespace="/chat")
async def load_messages(sid, data):
    """Load encrypted messages for a chat with pagination"""
    print("\n" + "="*50)
    print("📥 LOAD MESSAGES")
    print("="*50)
    
    chat_id = data.get("chat_id")
    limit = data.get("limit", 50)  # Default 50 messages
    offset = data.get("offset", 0)
    
    if not chat_id:
        await sio.emit(
            "load_messages_error",
            {"error": "chat_id required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "load_messages_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "load_messages_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    async with AsyncSessionLocal() as session:
        try:
            
            # Verify user is member and get joined_at
            member_check = await session.execute(
                select(ChatMember.user_id, ChatMember.joined_at)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            member_row = member_check.first()

            if not member_row:
                await sio.emit(
                    "load_messages_error",
                    {"error": "Not a member of this chat"},
                    to=sid,
                    namespace="/chat"
                )
                return

            
            # Load messages with sender info and encrypted keys
            result = await session.execute(
                select(
                    Message.id,
                    Message.chat_id,
                    Message.sender_id,
                    Message.kind,
                    Message.ciphertext,
                    Message.iv,
                    Message.is_encrypted,
                    Message.file_url,
                    Message.file_name,
                    Message.file_size,
                    Message.file_type,
                    Message.created_at,
                    User.username,
                    User.full_name,
                    MessageKey.encrypted_key
                )
                .join(User, Message.sender_id == User.user_id)
                .outerjoin(
                    MessageKey,
                    and_(
                        MessageKey.message_id == Message.id,
                        MessageKey.recipient_id == user_id
                    )
                )
                .where(Message.chat_id == chat_id)
                .where(Message.created_at >= member_row.joined_at)  # ✅ Hide pre-join messages
                .order_by(Message.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            messages_raw = result.all()
            
            # Format messages
            messages = []
            for msg in messages_raw:
                message_data = {
                    "id": msg.id,
                    "chat_id": msg.chat_id,
                    "sender_id": str(msg.sender_id),
                    "sender_username": msg.username,
                    "sender_full_name": msg.full_name,
                    "kind": msg.kind,
                    "ciphertext": msg.ciphertext,
                    "iv": msg.iv,
                    "is_encrypted": msg.is_encrypted,
                    "encrypted_key": msg.encrypted_key,  # This user's encrypted key
                    "file_url": msg.file_url,
                    "file_name": msg.file_name,
                    "file_size": msg.file_size,
                    "file_type": msg.file_type,
                    "created_at": msg.created_at.isoformat() + 'Z',
                    "is_own": str(msg.sender_id) == user_id_str
                }
                messages.append(message_data)
            
            # Reverse to show oldest first
            messages.reverse()
            
            # Get total message count for pagination
            count_result = await session.execute(
                select(func.count(Message.id))
                .where(Message.chat_id == chat_id)
                .where(Message.created_at >= member_row.joined_at)  # ✅ Correct count for pagination
            )
            total_messages = count_result.scalar()
            
            await sio.emit(
                "messages_loaded",
                {
                    "chat_id": chat_id,
                    "messages": messages,
                    "total": total_messages,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_messages
                },
                to=sid,
                namespace="/chat"
            )
            
            print(f"✅ Loaded {len(messages)} messages for chat {chat_id}")
            print(f"   Pagination: {offset}-{offset+len(messages)} of {total_messages}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit(
                "load_messages_error",
                {"error": "Failed to load messages"},
                to=sid,
                namespace="/chat"
            )
# ============================================================
# GET_CHAT_MEMBERS - Fetch all members of a chat
# ============================================================

@sio.event(namespace="/chat")
async def get_chat_members(sid, data):
    """
    Get all members of a chat with their details and online status.
    
    Expected data:
    {
        "chat_id": int
    }
    
    Emits:
        - "chat_members": Success with member list
        - "chat_members_error": Error
    """
    print("\n" + "="*50)
    print("👥 GET CHAT MEMBERS")
    print("="*50)
    
    chat_id = data.get("chat_id")
    
    if not chat_id:
        await sio.emit(
            "chat_members_error",
            {"error": "chat_id is required"},
            to=sid,
            namespace="/chat"
        )
        return
    
    # ✅ Get user_id as string first
    user_id_str = get_user_id_by_sid(sid)
    if not user_id_str:
        await sio.emit(
            "chat_members_error",
            {"error": "Not authenticated"},
            to=sid,
            namespace="/chat"
        )
        return
    
    # ✅ Convert to UUID for database operations
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid UUID: {user_id_str}")
        await sio.emit(
            "chat_members_error",
            {"error": "Invalid user ID"},
            to=sid,
            namespace="/chat"
        )
        return
    
    print(f"👤 Requester: {user_id_str}")
    print(f"💬 Chat: {chat_id}")
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Verify chat exists and is not archived
            chat_result = await session.execute(
                select(Chat.id, Chat.name, Chat.is_group, Chat.is_locked)
                .where(Chat.id == chat_id)
                .where(Chat.is_archived == False)
            )
            chat = chat_result.first()
            
            if not chat:
                await sio.emit(
                    "chat_members_error",
                    {"error": "Chat not found"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            # 2. Verify requester is a member of the chat
            member_check = await session.execute(
                select(ChatMember.user_id, ChatMember.is_admin)
                .where(ChatMember.chat_id == chat_id)
                .where(ChatMember.user_id == user_id)
            )
            requester_membership = member_check.first()
            
            if not requester_membership:
                await sio.emit(
                    "chat_members_error",
                    {"error": "You are not a member of this chat"},
                    to=sid,
                    namespace="/chat"
                )
                return
            
            is_requester_admin = requester_membership.is_admin
            
            # 3. Get all members with their user details
            members_result = await session.execute(
                select(
                    ChatMember.user_id,
                    ChatMember.is_admin,
                    ChatMember.is_blocked,
                    ChatMember.joined_at,
                    ChatMember.last_seen,
                    User.username,
                    User.full_name,
                    User.email,
                    User.public_key
                )
                .join(User, ChatMember.user_id == User.user_id)
                .where(ChatMember.chat_id == chat_id)
                .order_by(ChatMember.is_admin.desc(), User.username.asc())
            )
            
            members_raw = members_result.all()
            
            # 4. Format member list
            members = []
            for m in members_raw:
                member_id_str = str(m.user_id)
                
                member_data = {
                    "user_id": member_id_str,
                    "username": m.username,
                    "full_name": m.full_name,
                    "is_admin": m.is_admin,
                    "is_blocked": m.is_blocked,
                    "is_online": member_id_str in active_users,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    "last_seen": m.last_seen.isoformat() if m.last_seen else None,
                    "is_you": member_id_str == user_id_str
                }
                
                # Only include email and public_key for:
                # - The requester themselves
                # - Other members if it's a DM (for encryption)
                if member_id_str == user_id_str or not chat.is_group:
                    member_data["email"] = m.email
                    member_data["public_key"] = m.public_key
                
                members.append(member_data)
            
            # 5. Get online count
            online_count = sum(1 for m in members if m["is_online"])
            
            # 6. Emit success
            await sio.emit(
                "chat_members",
                {
                    "chat_id": chat_id,
                    "chat_name": chat.name,
                    "is_group": chat.is_group,
                    "is_locked": chat.is_locked,
                    "members": members,
                    "total_members": len(members),
                    "online_count": online_count,
                    "is_admin": is_requester_admin
                },
                to=sid,
                namespace="/chat"
            )
            
            print(f"✅ Sent {len(members)} members for chat {chat_id}")
            print(f"   Online: {online_count}/{len(members)}")
            
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await sio.emit(
                "chat_members_error",
                {"error": "Failed to fetch chat members"},
                to=sid,
                namespace="/chat"
            )


def register_socket_events():
    """Events registered via decorators - this is a placeholder"""
    logger.info("✅ Socket.IO events active")