"use client"

import { useEffect, useState, useRef } from "react"
import { useRouter, useParams } from "next/navigation"
import { socket } from "@/lib/socket"
import { useAppStore } from "@/lib/store"
import { encryptMessage, decryptMessage } from "@/lib/crypto"
import { MessageBubble } from "@/components/chat/MessageBubble"
import { MessageInput } from "@/components/chat/MessageInput"
import { AdminControls } from "@/components/chat/AdminControls"
import { Button } from "@/components/ui/common"
import { Loader2, Lock, Users, Shield, ShieldOff, UserX, LogOut } from "lucide-react"

interface Member {
  user_id: string
  username: string
  is_admin: boolean
}

export default function ChatRoomPage() {
  const params = useParams()
  const chatId = Number(params.chatId)
  const router = useRouter()
  const { messages, addMessage, setMessages, privateKey, currentUser, chats, removeChat, addAvailableChat } = useAppStore()

  const [isLoading, setIsLoading] = useState(true)
  const [publicKeys, setPublicKeys] = useState<{ [userId: string]: string }>({})
  const [members, setMembers] = useState<Member[]>([])
  const [memberCount, setMemberCount] = useState(0)
  const [showMembers, setShowMembers] = useState(false)
  const [isExiting, setIsExiting] = useState(false) // Prevent operations during exit/delete
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const chatMessages = messages[chatId] || []
  const currentChat = chats.find((c) => c.chat_id === chatId)
  const isAdmin = currentChat?.is_admin || false

  // 1. Enter Chat & Load Data
  useEffect(() => {
    // Guard: Don't do anything if we're exiting or not connected
    if (isExiting || !socket.connected) {
      if (!socket.connected) {
        router.push("/connect")
      }
      return
    }

    setIsLoading(true)

    // Join room
    socket.emit("enter_chat", { chat_id: chatId })

    // Get keys for encryption
    socket.emit("get_chat_public_keys", { chat_id: chatId })

    // Listeners
    socket.on("enter_chat_error", (error) => {
      console.error("❌ Enter chat error:", error)
      setIsLoading(false)
      alert(`Failed to enter chat: ${error.error}`)
    })

    socket.on("entered_chat", async (data) => {
      // Decrypt initial messages
      const decryptedMessages = await Promise.all(
        data.messages.map(async (msg: any) => {
          if (msg.is_encrypted && msg.ciphertext && msg.encrypted_key && privateKey) {
            try {
              const content = await decryptMessage(msg.ciphertext, msg.iv || "", msg.encrypted_key, privateKey)
              return { ...msg, decryptedContent: content }
            } catch (e) {
              console.error("Failed to decrypt history:", e)
              return { ...msg, decryptedContent: "[Decryption Failed]" }
            }
          }
          return { ...msg, decryptedContent: msg.ciphertext }
        }),
      )

      setMessages(chatId, decryptedMessages)

      // Set members if provided (backend might need update to send members on enter_chat,
      // but for now we can fetch them or rely on what we have.
      // Let's assume we might need a separate fetch or the backend sends it.
      // Checking backend: enter_chat sends messages. We might need to fetch members separately or update backend.
      // For now, let's assume we can get members via a new event or just rely on what we have.
      // Actually, let's add a fetch members call if needed, but for now let's see if we can get by.
      // Wait, we need members for the member list.
      // Let's emit 'get_chat_members' if it exists, or just use what we have.
      // Backend doesn't seem to have 'get_chat_members'.
      // We'll implement a simple member fetch in the useEffect if needed,
      // but for now let's just use a placeholder or assume we can get it.
      // Actually, let's add a fetch for members.
      // socket.emit('get_chat_members', { chat_id: chatId });
      // Since we can't easily change backend right now without context,
      // let's check if 'entered_chat' has members.
      // Backend 'enter_chat' sends: messages, chat_id.
      // We might need to add a 'get_members' event to backend or just use 'get_chat_public_keys' which returns keys.
      // 'get_chat_public_keys' returns { chat_id, public_keys }. Keys are user_id -> key.
      // We can use that to at least know WHO is in the chat, but not their names/admin status.
      // Let's check 'load_chats' - it gives member_chats but not member lists.
      // Okay, we need a way to get members.
      // Let's use 'get_dm_partner_info' logic but for groups? No.
      // Let's assume for this task we might need to add a backend event or use an existing one.
      // 'admin_delete_chat' etc are there.
      // Let's add a simple 'get_chat_details' to backend if possible, or just use 'get_chat_public_keys' keys for now
      // and maybe we can't show full names yet without fetching profiles.
      // Wait, `enter_chat` in backend:
      // It sends messages.
      // We really need a member list.
      // Let's look at `socket_events.py` again.
      // There is no specific `get_members`.
      // However, we can use `get_chat_public_keys` to get IDs.
      // Then `get_users_by_ids`? No.
      // Let's just use the `publicKeys` state to populate a basic list for now,
      // and maybe we can't show full names/admin status without backend change.
      // BUT, the user asked for admin functionalities including remove member.
      // So we MUST see the members.
      // I will add a `get_chat_members` event to the backend in the next step if it's missing.
      // For now, I'll add the UI code assuming we can get the list.

      setIsLoading(false)
      scrollToBottom()
    })

    socket.on("chat_public_keys", (data) => {
      if (data.chat_id === chatId) {
        setPublicKeys(data.public_keys)
        // Temporary: populate members from keys just to show something
        // In reality we need names and admin status.
        // We'll implement a proper fetch in the next step.
      }
    })

    socket.on("new_message", async (msg) => {
      if (msg.chat_id !== chatId) return

      let decryptedContent = msg.ciphertext
      if (msg.is_encrypted && privateKey) {
        try {
          decryptedContent = await decryptMessage(msg.ciphertext, msg.iv, msg.encrypted_key, privateKey)
        } catch (e) {
          console.error("Failed to decrypt new message:", e)
          decryptedContent = "[Decryption Failed]"
        }
      }

      addMessage(chatId, { ...msg, decryptedContent })
      scrollToBottom()
    })

    socket.on("send_message_error", (error) => {
      console.error("[SEND] Error from server:", error)
      alert(`Failed to send message: ${error.error}`)
    })

    socket.on("message_sent", (data) => {
      console.log("[SEND] Message sent successfully:", data)
    })

    // Admin Events
    socket.on("chat_deleted", (data) => {
      // Prevent further operations
      setIsExiting(true)

      // Remove chat from local state immediately
      removeChat(chatId)

      // Navigate first to unmount component
      router.replace("/chat")

      // Show message after navigation starts
      setTimeout(() => alert(data.message), 100)
    })

    socket.on("chat_deleted_success", (data) => {
      // Prevent further operations
      setIsExiting(true)

      // Remove chat from local state
      removeChat(chatId)

      // Navigate first
      router.replace("/chat")

      // Show message after
      setTimeout(() => alert("Chat deleted successfully"), 100)
    })

    socket.on("member_removed", (data) => {
      if (data.chat_id === chatId) {
        console.log("Member removed from chat:", data)
        setMemberCount((prev) => prev - 1)
        // Refresh members list
        socket.emit("get_chat_members", { chat_id: chatId })
      }
    })

    // Handle when current user is removed by admin
    socket.on("removed_from_chat", (data) => {
      if (data.chat_id === chatId) {
        // Prevent further operations
        setIsExiting(true)

        // Remove chat from local state
        removeChat(chatId)

        // Navigate first
        router.replace("/chat")

        // Show message after
        setTimeout(() => alert(data.message || "You have been removed from this chat"), 100)
      }
    })

    // Admin confirmation for successful removal
    socket.on("member_removed_success", (data) => {
      console.log("Member removed successfully:", data)
      // Member list already refreshed by member_removed event
    })

    // Handle admin action errors
    socket.on("admin_action_error", (error) => {
      alert(error.error || "Admin action failed")
    })

    socket.on("member_promoted", (data) => {
      socket.emit("get_chat_members", { chat_id: chatId })
    })

    socket.on("member_demoted", (data) => {
      socket.emit("get_chat_members", { chat_id: chatId })
    })

    // Listen for new members joining (after join request approval)
    socket.on("user_joined_chat", (data) => {
      if (data.chat_id === chatId) {
        console.log("New member joined:", data)
        setMemberCount((prev) => prev + 1)
        // Refresh member list
        socket.emit("get_chat_members", { chat_id: chatId })
      }
    })

    // Custom event listener for our new get_chat_members event
    socket.on("chat_members", (data) => {
      setMembers(data.members)
      setMemberCount(data.total_members || data.members.length)
    })

    // Exit Group Events  
    socket.on("exit_group_success", (data) => {
      // Prevent further operations
      setIsExiting(true)

      // Add to available chats if it's a public group
      if (currentChat?.is_group && !currentChat?.is_locked) {
        addAvailableChat({
          chat_id: chatId,
          name: currentChat.name,
          is_locked: false,
          created_by: "" // We don't have this info, but it's not critical for display
        })
      }

      // Remove the chat from member chats
      removeChat(chatId)

      // Navigate first to unmount component
      router.replace("/chat")

      // Show message after navigation starts
      setTimeout(() => alert(data.message || "You have left the group"), 100)
    })

    socket.on("exit_group_error", (error) => {
      alert(error.error || "Failed to exit group")
    })

    // Initial fetch (we'll implement backend handler next)
    socket.emit("get_chat_members", { chat_id: chatId })

    return () => {
      socket.emit("leave_chat", { chat_id: chatId })
      socket.off("entered_chat")
      socket.off("chat_public_keys")
      socket.off("new_message")
      socket.off("send_message_error")
      socket.off("message_sent")
      socket.off("chat_deleted")
      socket.off("chat_deleted_success")
      socket.off("member_removed")
      socket.off("removed_from_chat")
      socket.off("member_removed_success")
      socket.off("admin_action_error")
      socket.off("member_promoted")
      socket.off("member_demoted")
      socket.off("chat_members")
      socket.off("exit_group_success")
      socket.off("exit_group_error")
    }
  }, [chatId, router, setMessages, addMessage, privateKey, chats, isExiting, currentChat, removeChat, addAvailableChat])

  const scrollToBottom = () => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }, 100)
  }

  const handleSend = async (text: string, file?: File) => {
    if (!currentUser) return

    try {
      let fileUrl = ""
      let fileName = ""
      let fileSize = 0
      let fileType = ""
      let kind: "text" | "image" | "file" = "text"

      if (file) {
        const formData = new FormData()
        formData.append("file", file)

        const authToken = (socket.auth as any)?.token || ""
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/upload`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
          body: formData,
        })

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}))
          throw new Error(errorData.detail || "Upload failed")
        }
        const data = await res.json()
        fileUrl = data.file_url
        fileName = data.file_name
        fileSize = data.file_size
        fileType = data.file_type
        kind = file.type.startsWith("image/") ? "image" : "file"
      }

      const { ciphertext, iv, encrypted_keys } = await encryptMessage(
        text || (file ? "[File Attachment]" : ""),
        publicKeys,
      )

      socket.emit("send_message", {
        chat_id: chatId,
        ciphertext,
        iv,
        encrypted_keys,
        kind,
        file_url: fileUrl,
        file_name: fileName,
        file_size: fileSize,
        file_type: fileType,
      })
    } catch (error) {
      console.error("Send failed:", error)
      alert("Failed to send message")
    }
  }

  const handleAdminAction = (action: "promote" | "demote" | "remove", memberId: string) => {
    if (!confirm(`Are you sure you want to ${action} this user?`)) return

    const eventMap = {
      promote: "admin_promote_member",
      demote: "admin_demote_member",
      remove: "admin_remove_member",
    }

    socket.emit(eventMap[action], {
      chat_id: chatId,
      member_id: memberId,
    })
  }

  const handleExitGroup = () => {
    if (!confirm("Are you sure you want to leave this group?")) return

    socket.emit("exit_group", {
      chat_id: chatId,
    })
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full relative">
      {/* Header */}
      <div className="p-4 border-b border-cyan-400/10 flex items-center justify-between bg-white/5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-cyan-500/10 flex items-center justify-center">
            {currentChat?.is_group ? (
              <Users className="h-5 w-5 text-cyan-400" />
            ) : (
              <Lock className="h-5 w-5 text-cyan-400" />
            )}
          </div>
          <div>
            <h2 className="font-bold text-white">{currentChat?.name || `Chat ${chatId}`}</h2>
            <div className="flex items-center gap-2 text-xs text-white/50">
              <span>{memberCount} members</span>
              {currentChat?.is_group && (
                <button onClick={() => setShowMembers(true)} className="hover:text-cyan-400 transition-colors">
                  View Members
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Exit Group button for non-admin members only */}
          {!isAdmin && currentChat?.is_group && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExitGroup}
              className="text-red-400 hover:bg-red-400/10 hover:text-red-300"
            >
              <LogOut className="h-4 w-4 mr-2" />
              Exit Group
            </Button>
          )}

          {/* Admin controls for admins only */}
          {isAdmin && currentChat?.is_group && (
            <AdminControls chatId={chatId} isGroup={currentChat.is_group} chatName={currentChat.name} />
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} isOwn={!!msg.is_own} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <MessageInput onSend={handleSend} />

      {/* Members Modal */}
      {showMembers && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}
        >
          <div className="w-full max-w-md glass rounded-xl shadow-2xl overflow-hidden" style={{ margin: "auto" }}>
            <div className="p-4 border-b border-cyan-400/10 flex items-center justify-between">
              <h3 className="font-semibold text-white">Chat Members</h3>
              <Button variant="ghost" size="sm" onClick={() => setShowMembers(false)}>
                Close
              </Button>
            </div>
            <div className="p-2 max-h-[60vh] overflow-y-auto">
              {members.map((member) => (
                <div
                  key={member.user_id}
                  className="flex items-center justify-between p-3 hover:bg-white/5 rounded-lg group transition-smooth"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold text-sm">
                      {member.username[0].toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-white flex items-center gap-2">
                        {member.username}
                        {member.is_admin && <Shield className="h-3 w-3 text-cyan-400" />}
                      </p>
                    </div>
                  </div>

                  {isAdmin && currentUser?.user_id !== member.user_id && (
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {member.is_admin ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-orange-400 hover:bg-orange-400/10"
                          title="Demote to Member"
                          onClick={() => handleAdminAction("demote", member.user_id)}
                        >
                          <ShieldOff className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-green-400 hover:bg-green-400/10"
                          title="Promote to Admin"
                          onClick={() => handleAdminAction("promote", member.user_id)}
                        >
                          <Shield className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-red-400 hover:bg-red-400/10"
                        title="Remove from Chat"
                        onClick={() => handleAdminAction("remove", member.user_id)}
                      >
                        <UserX className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
