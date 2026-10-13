"use client"

import type React from "react"

import { useEffect, useState, useMemo } from "react"
import { useRouter, usePathname } from "next/navigation"
import { socket } from "@/lib/socket"
import { useAppStore } from "@/lib/store"
import { LogOut, Plus, MessageSquare, Users, Lock, Search } from "lucide-react"
import { Button } from "@/components/ui/common"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { Suspense } from "react"
import { SelectUserModal } from "@/components/chat/SelectUserModal"

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { chats, availableChats, currentUser } = useAppStore()
  const [searchQuery, setSearchQuery] = useState("")
  const [showUserModal, setShowUserModal] = useState(false)

  useEffect(() => {
    if (!socket.connected) {
      router.push("/connect")
      return
    }

    socket.on("create_room_success", (data) => {
      useAppStore.getState().setChats([data.room, ...useAppStore.getState().chats])
      router.push(`/chat/${data.room.chat_id}`)
    })

    socket.on("create_room_error", (error) => {
      alert(`Failed to create chat: ${error.error}`)
    })

    socket.on("new_group_available", (data) => {
      const current = useAppStore.getState().availableChats
      useAppStore.getState().setAvailableChats([data, ...current])
    })

    // Handle join request responses
    socket.on("join_request_submitted", (data) => {
      if (data.auto_approved || data.status === "approved") {
        // Chat was auto-approved (public group) - add to user's chats immediately
        const newChat = {
          chat_id: data.chat_id,
          name: data.chat_name,
          is_group: true,
          is_locked: false,
          is_admin: false,
        }

        // Add to user's chats
        useAppStore.getState().setChats([newChat, ...useAppStore.getState().chats])

        // Remove from available chats
        const filtered = useAppStore.getState().availableChats.filter((c) => c.chat_id !== data.chat_id)
        useAppStore.getState().setAvailableChats(filtered)

        // Show success
        alert(data.message || "You have joined the group!")

        // Wait a moment for backend to finish processing, then navigate
        // This prevents race condition where enter_chat fails because membership isn't committed yet
        setTimeout(() => {
          router.push(`/chat/${data.chat_id}`)
        }, 500)
      } else {
        // Join request pending approval (locked group)
        alert(data.message || "Join request sent. Waiting for admin approval.")
      }
    })

    socket.on("join_request_error", (error) => {
      alert(error.error || "Failed to join chat")
    })

    return () => {
      socket.off("create_room_success")
      socket.off("create_room_error")
      socket.off("new_group_available")
      socket.off("join_request_submitted")
      socket.off("join_request_error")
    }
  }, [router])

  const handleCreateChat = () => {
    const isGroup = confirm("Create a group chat? (Cancel for Direct Message)")

    if (isGroup) {
      // Group chat flow
      const roomName = prompt("Enter group name:")
      if (!roomName || roomName.trim() === "") return

      const isLocked = confirm("Should this group be locked (private)?")

      socket.emit("create_room", {
        room_name: roomName.trim(),
        is_group: true,
        is_locked: isLocked,
      })
    } else {
      // Direct message flow - show user selection modal
      setShowUserModal(true)
    }
  }

  const handleCreateDM = async (targetUserId: string) => {
    try {
      const authToken = (socket.auth as any)?.token || ""

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/dm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ target_user_id: targetUserId }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to create DM")
      }

      const data = await response.json()

      // Add or update chat in store
      const dmChat = {
        chat_id: data.chat_id,
        name: data.partner.username,
        is_group: false,
        is_locked: true,
        is_admin: true,
      }

      // Check if chat already exists in list
      const existingChatIndex = chats.findIndex((c) => c.chat_id === data.chat_id)

      if (existingChatIndex === -1) {
        // New chat - add to list
        useAppStore.getState().setChats([dmChat, ...chats])
      }

      // Navigate to the DM
      router.push(`/chat/${data.chat_id}`)

      if (data.is_new) {
        alert(`Started new conversation with ${data.partner.username}`)
      }
    } catch (error) {
      console.error("Failed to create DM:", error)
      alert(error instanceof Error ? error.message : "Failed to create direct message")
    }
  }

  const handleJoinChat = (chatId: number) => {
    socket.emit("join_request", { chat_id: chatId })
    // Alert will be shown by event listener based on response
  }

  // Filter chats based on search query
  const filteredChats = useMemo(() => {
    if (!searchQuery.trim()) return chats
    const query = searchQuery.toLowerCase()
    return chats.filter(
      (chat) => chat.name?.toLowerCase().includes(query) || `chat ${chat.chat_id}`.toLowerCase().includes(query),
    )
  }, [chats, searchQuery])

  const filteredAvailableChats = useMemo(() => {
    if (!searchQuery.trim()) return availableChats
    const query = searchQuery.toLowerCase()
    return availableChats.filter((chat) => chat.name?.toLowerCase().includes(query))
  }, [availableChats, searchQuery])

  return (
    <div className="flex h-screen overflow-hidden">
      <Suspense fallback={<div>Loading...</div>}>
        <aside
          className={cn(
            "w-full md:w-96 flex flex-col glass border-r border-cyan-400/10 transition-smooth",
            pathname !== "/chat" && "hidden md:flex",
          )}
        >
          {/* Header */}
          <div className="p-6 border-b border-cyan-400/10">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold">
                  <span className="bg-gradient-to-r from-cyan-300 to-cyan-200 bg-clip-text text-transparent">
                    Secure
                  </span>
                </h1>
                <p className="text-xs text-white/50 mt-1">End-to-end encrypted chat</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  socket.disconnect()
                  useAppStore.getState().resetStore()
                  router.push("/connect")
                }}
                className="text-white/50 hover:text-white hover:bg-white/5"
                title="Logout"
              >
                <LogOut className="h-5 w-5" />
              </Button>
            </div>

            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30" />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-white/5 border border-cyan-400/20 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-smooth"
              />
            </div>

            <Button
              onClick={handleCreateChat}
              className="w-full bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white shadow-lg shadow-cyan-500/20"
              size="lg"
            >
              <Plus className="h-4 w-4" />
              New Chat
            </Button>
          </div>

          {/* Chat List */}
          <div className="flex-1 overflow-y-auto">
            {/* Your Chats */}
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Lock className="h-4 w-4 text-cyan-400" />
                <h3 className="text-xs font-semibold text-white/70 uppercase tracking-wide">Your Chats</h3>
              </div>

              <div className="space-y-1">
                {filteredChats.map((chat) => (
                  <Link
                    key={chat.chat_id}
                    href={`/chat/${chat.chat_id}`}
                    className={cn(
                      "block px-4 py-3 rounded-lg transition-smooth group",
                      pathname === `/chat/${chat.chat_id}`
                        ? "bg-cyan-600/15 border border-cyan-400/30 shadow-lg shadow-cyan-500/5"
                        : "hover:bg-white/5 border border-transparent",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {chat.is_group ? (
                          <Users className="h-4 w-4 text-cyan-400 shrink-0" />
                        ) : (
                          <MessageSquare className="h-4 w-4 text-cyan-400 shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-white truncate">
                              {chat.name || `Chat ${chat.chat_id}`}
                            </p>
                            {chat.is_locked && <Lock className="h-3 w-3 text-white/30 shrink-0" />}
                          </div>
                          <p className="text-xs text-white/40">{chat.is_group ? "Group" : "Direct"}</p>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
                {filteredChats.length === 0 && (
                  <p className="px-4 py-8 text-xs text-white/30 text-center">
                    {searchQuery ? "No chats found" : "No chats yet"}
                  </p>
                )}
              </div>
            </div>

            {/* Available Groups */}
            {filteredAvailableChats.length > 0 && (
              <div className="p-4 border-t border-cyan-400/10">
                <h3 className="text-xs font-semibold text-white/70 uppercase tracking-wide mb-3">Available Groups</h3>

                <div className="space-y-1">
                  {filteredAvailableChats.map((chat) => (
                    <div
                      key={chat.chat_id}
                      className="px-4 py-3 rounded-lg hover:bg-white/5 transition-smooth border border-transparent hover:border-cyan-400/20"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <Users className="h-4 w-4 text-white/40 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">{chat.name}</p>
                            <p className="text-xs text-white/40">Group</p>
                          </div>
                        </div>
                        <Button
                          onClick={() => handleJoinChat(chat.chat_id)}
                          size="sm"
                          className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs"
                        >
                          Join
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>
      </Suspense>

      {/* Main Content */}
      <main className={cn("flex-1 relative", pathname === "/chat" && "hidden md:block")}>{children}</main>

      {/* Select User Modal */}
      <SelectUserModal
        isOpen={showUserModal}
        onClose={() => setShowUserModal(false)}
        onSelectUser={handleCreateDM}
        authToken={(socket.auth as any)?.token || ""}
      />
    </div>
  )
}
