"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/common"
import { Search, X, MessageSquare, Loader2 } from "lucide-react"

interface User {
    user_id: string
    username: string
    full_name: string
    email: string
}

interface SelectUserModalProps {
    isOpen: boolean
    onClose: () => void
    onSelectUser: (userId: string) => void
    authToken: string
}

export function SelectUserModal({ isOpen, onClose, onSelectUser, authToken }: SelectUserModalProps) {
    const [searchQuery, setSearchQuery] = useState("")
    const [users, setUsers] = useState<User[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState("")

    useEffect(() => {
        if (!isOpen) {
            setSearchQuery("")
            setUsers([])
            setError("")
            return
        }
    }, [isOpen])

    useEffect(() => {
        const searchUsers = async () => {
            if (searchQuery.trim().length < 2) {
                setUsers([])
                return
            }

            setIsLoading(true)
            setError("")

            try {
                const response = await fetch(
                    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/users/search?query=${encodeURIComponent(searchQuery)}`,
                    {
                        headers: {
                            Authorization: `Bearer ${authToken}`,
                        },
                    }
                )

                if (!response.ok) {
                    throw new Error("Failed to search users")
                }

                const data = await response.json()
                setUsers(data.users || [])
            } catch (err) {
                console.error("Search error:", err)
                setError("Failed to search users")
                setUsers([])
            } finally {
                setIsLoading(false)
            }
        }

        const debounce = setTimeout(searchUsers, 300)
        return () => clearTimeout(debounce)
    }, [searchQuery, authToken])

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-md glass rounded-xl shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="p-4 border-b border-cyan-400/10 flex items-center justify-between">
                    <h3 className="font-semibold text-white">Select User for Direct Message</h3>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                {/* Search */}
                <div className="p-4 border-b border-cyan-400/10">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/30" />
                        <input
                            type="text"
                            placeholder="Search by username or name..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full bg-white/5 border border-cyan-400/20 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-smooth"
                            autoFocus
                        />
                    </div>
                    {searchQuery.trim().length > 0 && searchQuery.trim().length < 2 && (
                        <p className="text-xs text-white/40 mt-2">Type at least 2 characters to search</p>
                    )}
                </div>

                {/* User List */}
                <div className="p-2 max-h-[400px] overflow-y-auto">
                    {isLoading && (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
                        </div>
                    )}

                    {error && (
                        <div className="text-center py-8">
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    {!isLoading && !error && searchQuery.trim().length >= 2 && users.length === 0 && (
                        <div className="text-center py-8">
                            <p className="text-sm text-white/40">No users found</p>
                        </div>
                    )}

                    {!isLoading && !error && searchQuery.trim().length < 2 && (
                        <div className="text-center py-8">
                            <Search className="h-8 w-8 text-white/20 mx-auto mb-2" />
                            <p className="text-sm text-white/40">Search for users to start a direct message</p>
                        </div>
                    )}

                    {!isLoading && users.map((user) => (
                        <div
                            key={user.user_id}
                            className="flex items-center justify-between p-3 hover:bg-white/5 rounded-lg group transition-smooth cursor-pointer"
                            onClick={() => {
                                onSelectUser(user.user_id)
                                onClose()
                            }}
                        >
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                <div className="h-10 w-10 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold">
                                    {user.username[0].toUpperCase()}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-white truncate">{user.username}</p>
                                    <p className="text-xs text-white/40 truncate">{user.full_name}</p>
                                </div>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                className="opacity-0 group-hover:opacity-100 transition-opacity text-cyan-400 hover:bg-cyan-400/10"
                            >
                                <MessageSquare className="h-4 w-4 mr-2" />
                                Message
                            </Button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
