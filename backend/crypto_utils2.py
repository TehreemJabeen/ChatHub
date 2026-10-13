from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select
from db.database import AsyncSessionLocal, User
from datetime import datetime

async def ensure_user_keys(user_id: str):
    """
    Ensures the user has an RSA key pair.
    If the public_key is missing, generates a new pair and stores the public key.
    Returns the public key (PEM string) and private key (PEM string) for client.
    """
    async with AsyncSessionLocal() as session:
        # 1️⃣ Fetch user
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # 2️⃣ Check if public key already exists
        if user.public_key:
            print(f"User {user_id} already has a public key, skipping generation.")
            return user.public_key, None  # private key stays only on client

        # 3️⃣ Generate new RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        public_key = private_key.public_key()

#msg encrypted and decrypted using AES key, AES key encryption: public key and decryption: private key

        # 4️⃣ Convert keys to PEM strings
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode() # decode func convert bytes ti string

        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        # 5️⃣ Save public key to DB
        user.public_key = pub_pem
        user.updated_at = datetime.utcnow()
        session.add(user)
        await session.commit()
        print(f"Generated new key pair for user {user_id}")

        # 6️⃣ Return keys (private key sent to client)
        return pub_pem, priv_pem

# ==================== RSA KEYS ====================
def generate_rsa_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048, #size of RSA key in bits
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key

# Convert Python’s private_key object → readable PEM string
def serialize_private_key(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

def serialize_public_key(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

# ==================== AES + RSA HYBRID ====================
def encrypt_message(message_text, recipient_public_keys):
    """
    Encrypt message with AES, then encrypt AES key with each recipient's public key.
    recipient_public_keys: dict {user_id: public_key_obj}
    Returns:
        ciphertext_b64, encrypted_keys [{recipient_id, encrypted_key}]
    """
    # 1️⃣ Generate random AES key
    aes_key = os.urandom(32)  # 256-bit

    # 2️⃣ AES encryption (CBC + PKCS7)
    iv = os.urandom(16)
    padder = sym_padding.PKCS7(128).padder()
    padded_data = padder.update(message_text.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Store iv + ciphertext together
    aes_payload = iv + ciphertext
    ciphertext_b64 = b64encode(aes_payload).decode()

    # 3️⃣ Encrypt AES key with recipient's RSA public key
    encrypted_keys = []
    for user_id, pub_key in recipient_public_keys.items():
        enc_key = pub_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        encrypted_keys.append({
            "recipient_id": user_id,
            "encrypted_key": b64encode(enc_key).decode()
        })

    return ciphertext_b64, encrypted_keys


# def decrypt_message(ciphertext_b64, encrypted_key_b64, private_key):
#     """
#     Decrypt AES key using RSA private key, then decrypt message using AES.
#     """
#     # 1️⃣ Decrypt AES key
#     enc_key = b64decode(encrypted_key_b64)
#     aes_key = private_key.decrypt(
#         enc_key,
#         padding.OAEP(
#             mgf=padding.MGF1(algorithm=hashes.SHA256()),
#             algorithm=hashes.SHA256(),
#             label=None
#         )
#     )

#     # 2️⃣ Decrypt message
#     aes_payload = b64decode(ciphertext_b64)
#     iv = aes_payload[:16]
#     ciphertext = aes_payload[16:]
#     cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
#     decryptor = cipher.decryptor()
#     padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

#     unpadder = sym_padding.PKCS7(128).unpadder()
#     plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

#     return plaintext.decode()

# @sio.event(namespace="/chat")
# async def typing_start(sid, data):
#     """Broadcast typing indicator"""
#     chat_id = data.get("chat_id")
#     user_id_str = get_user_id_by_sid(sid)  # ✅ FIX: Get string
    
#     if user_id_str and chat_id:
#         await sio.emit(
#             "user_typing",
#             {"user_id": user_id_str, "chat_id": chat_id},  # ✅ String
#             room=f"chat_{chat_id}",
#             skip_sid=sid,
#             namespace="/chat"
#         )


# @sio.event(namespace="/chat")
# async def typing_stop(sid, data):
#     """Broadcast typing stopped"""
#     chat_id = data.get("chat_id")
#     user_id_str = get_user_id_by_sid(sid)  # ✅ FIX: Get string
    
#     if user_id_str and chat_id:
#         await sio.emit(
#             "user_stopped_typing",
#             {"user_id": user_id_str, "chat_id": chat_id},  # ✅ String
#             room=f"chat_{chat_id}",
#             skip_sid=sid,
#             namespace="/chat"
#         )




# @sio.event(namespace="/chat")
# async def mark_read(sid, data):
#     """Mark messages as read"""
#     chat_id = data.get("chat_id")
#     last_read_id = data.get("last_read_id")
    
#     # ✅ FIX: Get both formats
#     user_id_str = get_user_id_by_sid(sid)
    
#     if not all([chat_id, last_read_id, user_id_str]):
#         return
    
#     try:
#         user_id = UUID(user_id_str)
#     except ValueError:
#         logger.error(f"Invalid UUID: {user_id_str}")
#         return
    
#     async with AsyncSessionLocal() as session:
#         # ✅ Use UUID for DB
#         await session.execute(
#             ChatMember.__table__.update()
#             .where(ChatMember.chat_id == chat_id)
#             .where(ChatMember.user_id == user_id)  # UUID
#             .values(last_seen=datetime.utcnow())
#         )
#         await session.commit()
    
#     # Notify others - ✅ Use string
#     await sio.emit(
#         "message_read",
#         {"user_id": user_id_str, "chat_id": chat_id, "last_read_id": last_read_id},
#         room=f"chat_{chat_id}",
#         skip_sid=sid,
#         namespace="/chat"
#     )

### **1. Test Suite - Remove Membe

# ============================================================
# GET_DM_PARTNER_INFO - ⚠️ NEEDS FIXES
# ============================================================

# @sio.event(namespace="/chat")
# async def get_dm_partner_info(sid, data):
#     """Get information about the other person in a DM"""
#     logger.info(f"🔍 Get DM partner info: {data}")
    
#     chat_id = data.get("chat_id")
    
#     if not chat_id:
#         await sio.emit("dm_partner_info_error", {"error": "chat_id is required"}, to=sid, namespace="/chat")
#         return
    
#     # ✅ FIX: Get both formats
#     user_id_str = get_user_id_by_sid(sid)
#     if not user_id_str:
#         await sio.emit("dm_partner_info_error", {"error": "Not authenticated"}, to=sid, namespace="/chat")
#         return
    
#     try:
#         user_id = UUID(user_id_str)
#     except ValueError:
#         logger.error(f"Invalid UUID: {user_id_str}")
#         await sio.emit("dm_partner_info_error", {"error": "Invalid user ID"}, to=sid, namespace="/chat")
#         return
    
#     async with AsyncSessionLocal() as session:
#         try:
#             # 1. Verify it's a DM
#             chat_result = await session.execute(
#                 select(Chat.is_group)
#                 .where(Chat.id == chat_id)
#                 .where(Chat.is_archived == False)
#             )
#             chat = chat_result.first()
            
#             if not chat:
#                 await sio.emit("dm_partner_info_error", {"error": "Chat not found"}, to=sid, namespace="/chat")
#                 return
            
#             if chat.is_group:
#                 await sio.emit("dm_partner_info_error", {"error": "This is a group chat, not a DM"}, to=sid, namespace="/chat")
#                 return
            
#             # 2. Verify user is member - ✅ Use UUID
#             member_check = await session.execute(
#                 select(ChatMember.user_id)
#                 .where(ChatMember.chat_id == chat_id)
#                 .where(ChatMember.user_id == user_id)  # UUID
#             )
            
#             if not member_check.scalar_one_or_none():
#                 await sio.emit("dm_partner_info_error", {"error": "Not a member of this chat"}, to=sid, namespace="/chat")
#                 return
            
#             # 3. Get the other user (partner) - ✅ Use UUID
#             members_result = await session.execute(
#                 select(
#                     ChatMember.user_id,
#                     User.username,
#                     User.full_name,
#                     User.email,
#                     User.public_key
#                 )
#                 .join(User, ChatMember.user_id == User.user_id)
#                 .where(ChatMember.chat_id == chat_id)
#                 .where(ChatMember.user_id != user_id)  # UUID comparison
#             )
            
#             partner = members_result.first()
            
#             if not partner:
#                 await sio.emit("dm_partner_info_error", {"error": "Partner not found"}, to=sid, namespace="/chat")
#                 return
            
#             # 4. Send partner info - ✅ Convert to string
#             partner_id_str = str(partner.user_id)
            
#             await sio.emit(
#                 "dm_partner_info",
#                 {
#                     "chat_id": chat_id,
#                     "partner": {
#                         "user_id": partner_id_str,  # String
#                         "username": partner.username,
#                         "full_name": partner.full_name,
#                         "email": partner.email,
#                         "public_key": partner.public_key,
#                         "is_online": partner_id_str in active_users  # String comparison
#                     }
#                 },
#                 to=sid,
#                 namespace="/chat"
#             )
            
#             logger.info(f"✅ Sent DM partner info for chat {chat_id}")
            
#         except Exception as e:
#             logger.exception(f"❌ Failed to get DM partner info")
#             await sio.emit("dm_partner_info_error", {"error": "Failed to get partner info"}, to=sid, namespace="/chat")




@router.get("/users/me")
async def get_current_user_profile(user_id: str = Depends(get_current_user)):
    """Get current user's profile"""
    logger.info(f"Get profile: {user_id}")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": str(user.user_id),
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "public_key": user.public_key
        }



@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: int,
    before_id: Optional[int] = None,
    limit: int = Query(50, le=100),
    user_id: str = Depends(get_current_user)
):
    """Get chat message history"""
    logger.info(f"Get messages: chat={chat_id}, user={user_id}")
    
    async with AsyncSessionLocal() as session:
        member_check = await session.execute(
            select(ChatMember)
            .where(ChatMember.chat_id == chat_id)
            .where(ChatMember.user_id == user_id)
        )
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member")
        
        query = (
            select(
                Message.id, Message.sender_id, Message.kind,
                Message.ciphertext, Message.created_at,
                Message.file_url, Message.file_name, Message.file_size,
                User.username, User.full_name
            )
            .join(User, Message.sender_id == User.user_id)
            .where(Message.chat_id == chat_id)
        )
        
        if before_id:
            query = query.where(Message.id < before_id)
        
        query = query.order_by(desc(Message.created_at)).limit(limit)
        
        result = await session.execute(query)
        messages_raw = result.all()
        
        message_ids = [m.id for m in messages_raw]
        keys_map = {}
        
        if message_ids:
            keys_result = await session.execute(
                select(MessageKey.message_id, MessageKey.encrypted_key)
                .where(MessageKey.message_id.in_(message_ids))
                .where(MessageKey.recipient_id == user_id)
            )
            keys_map = {row.message_id: row.encrypted_key for row in keys_result.all()}
        
        messages = [
            {
                "id": m.id,
                "sender_id": str(m.sender_id),
                "sender_username": m.username,
                "sender_full_name": m.full_name,
                "kind": m.kind,
                "ciphertext": m.ciphertext,
                "encrypted_key": keys_map.get(m.id),
                "file_url": m.file_url,
                "file_name": m.file_name,
                "file_size": m.file_size,
                "created_at": m.created_at.isoformat(),
                "is_own": str(m.sender_id) == user_id
            }
            for m in reversed(messages_raw)
        ]
        
        return {
            "messages": messages,
            "has_more": len(messages_raw) == limit
        }
