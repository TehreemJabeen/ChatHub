# Chat Application API

A real-time, end-to-end encrypted chat backend using **FastAPI**, **Socket.IO**, and **PostgreSQL**.  
Supports JWT-based authentication via Supabase and AES+RSA hybrid message encryption.

---

## Table of Contents


1. [Features](#features)  
2. [Tech Stack](#tech-stack)  
3. [Database & Supabase](#database--supabase)  
4. [Database Schema Highlights](#db)  
5. [REST API Endpoints](#rest-api-endpoints)  
6. [Socket.IO Events](#socketio-events) 


---

## Features

- Real-time chat with **Socket.IO**  
- JWT authentication via **Supabase**  
- End-to-end **AES+RSA hybrid encryption** for messages  
- Public and private group chats  
- Direct messaging (DM) support  
- Join requests and approval for locked group chats  
- Message history retrieval with pagination using database 
- Upload and serve files per chat  
- Active user and session tracking  

---

## Tech Stack

- **Backend:** Python, FastAPI, Socket.IO  
- **Database:** PostgreSQL (via SQLAlchemy ORM)  
- **Authentication:** JWT (Supabase integration)  
- **Encryption:** Cryptography library (RSA & AES hybrid)  
- **Real-time communication:** WebSockets via Socket.IO  
 
## Database & Supabase

This project uses **PostgreSQL** as the primary database to store:

- Users  
- Chats & Chat Members  
- Messages & Message Keys  
- File attachments  

**Supabase** is used for:

- Authentication via JWT (sign-up, login)  
- Managing user sessions  

### Database Schema Highlights

| Table       | Purpose                                           |
|------------|---------------------------------------------------|
| `User`      | Stores user info & public key for encryption     |
| `Chat`      | Stores chat metadata (DM or group)              |
| `ChatMember`| Links users to chats with last-seen timestamps |
| `Message`   | Stores encrypted messages                        |
| `MessageKey`| Stores AES keys encrypted per recipient         |

Supabase makes authentication simple and provides a secure JWT-based flow, while PostgreSQL ensures reliable storage of messages and encryption keys.

## REST API Endpoints
---
| Endpoint                    | Method | Description                                  |
| --------------------------- | ------ | -------------------------------------------- |
| `/`                         | GET    | API info & endpoints                         |
| `/health`                   | GET    | Health check with active users               |
| `/users/me`                 | GET    | Get current user profile (requires JWT)      |
| `/chats/{chat_id}/messages` | GET    | Fetch chat message history with AES+RSA keys |

## Socket.IO Events
- Event	Description	Namespace
- connect	Establish Socket.IO connection with JWT	/chat
- disconnect	Track user disconnection	/chat
- create_room	Create group or direct chat	/chat
- join_request	Request to join locked group	/chat
- enter_chat	Join chat room and load messages	/chat
- leave_chat    Leave room (but stay member)
- send_message  Send encrypted message
- load_messages Pagination
- admin controls such as: admin_remove_member

