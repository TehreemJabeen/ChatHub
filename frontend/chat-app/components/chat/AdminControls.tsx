"use client"

import { useState, useEffect } from "react"
import { socket } from "@/lib/socket"
import { Button } from "@/components/ui/common"
import { Settings, Users, Trash2 } from "lucide-react"
import { JoinRequestsModal } from "./JoinRequestsModal"
import { useRouter } from "next/navigation"

interface AdminControlsProps {
  chatId: number
  isGroup: boolean
  chatName: string
}

export function AdminControls({ chatId, isGroup, chatName }: AdminControlsProps) {
  const router = useRouter()
  const [showRequests, setShowRequests] = useState(false)
  const [pendingCount, setPendingCount] = useState(0)
  const [showMenu, setShowMenu] = useState(false)

  useEffect(() => {
    if (!isGroup) return

    // Initial check
    socket.emit("get_pending_requests", { chat_id: chatId })

    const handleRequestsList = (data: { requests: any[] }) => {
      setPendingCount(data.requests.length)
    }

    const handleNewRequest = (data: { chat_id: number }) => {
      if (data.chat_id === chatId) {
        setPendingCount((prev) => prev + 1)
      }
    }

    const handleRequestProcessed = () => {
      // Re-fetch to be accurate or decrement
      socket.emit("get_pending_requests", { chat_id: chatId })
    }

    socket.on("pending_requests", handleRequestsList)
    socket.on("new_join_request", handleNewRequest)
    socket.on("request_processed", handleRequestProcessed) // ✅ Match backend event name

    return () => {
      socket.off("pending_requests", handleRequestsList)
      socket.off("new_join_request", handleNewRequest)
      socket.off("request_processed", handleRequestProcessed)
    }
  }, [chatId, isGroup])

  const handleDeleteChat = () => {
    if (confirm(`Are you sure you want to delete "${chatName}"? This cannot be undone.`)) {
      socket.emit("admin_delete_chat", { chat_id: chatId })
    }
  }

  if (!isGroup) return null

  return (
    <>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="relative text-white/70 hover:text-white hover:bg-cyan-400/10"
          onClick={() => setShowRequests(true)}
        >
          <Users className="h-4 w-4 mr-2" />
          Requests
          {pendingCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 w-4 bg-cyan-500 rounded-full text-[10px] flex items-center justify-center text-black font-bold">
              {pendingCount}
            </span>
          )}
        </Button>

        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            className="text-white/70 hover:text-white hover:bg-cyan-400/10"
            onClick={() => setShowMenu(!showMenu)}
          >
            <Settings className="h-4 w-4" />
          </Button>

          {showMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white/10 backdrop-blur-md rounded-lg shadow-xl z-50 py-1 border border-cyan-400/20">
                <button
                  className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-white/10 flex items-center gap-2 transition-colors"
                  onClick={() => {
                    handleDeleteChat()
                    setShowMenu(false)
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Chat
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <JoinRequestsModal chatId={chatId} isOpen={showRequests} onClose={() => setShowRequests(false)} />
    </>
  )
}
