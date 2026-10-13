"use client"

import type React from "react"

import { useState, useRef } from "react"
import { Send, Paperclip, X } from "lucide-react"
import { Button, Input } from "@/components/ui/common"

interface MessageInputProps {
  onSend: (text: string, file?: File) => void
  isLoading?: boolean
}

export function MessageInput({ onSend, isLoading }: MessageInputProps) {
  const [text, setText] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if ((!text.trim() && !file) || isLoading) return

    onSend(text, file || undefined)
    setText("")
    setFile(null)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0])
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-5 bg-white/5 border-t border-cyan-400/10">
      {file && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-white/5 rounded-lg w-fit border border-cyan-400/20">
          <span className="text-sm text-white/70 max-w-[200px] truncate">{file.name}</span>
          <button
            type="button"
            onClick={() => setFile(null)}
            className="text-white/40 hover:text-white/70 transition-smooth"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="p-2.5 text-white/40 hover:text-white/70 transition-smooth"
        >
          <Paperclip className="h-6 w-6" />
        </button>
        <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileSelect} />

        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 bg-white/5 border-cyan-400/20 focus:ring-cyan-400/20 focus:border-cyan-400/50 text-white placeholder-white/30 text-base py-3 px-4"
        />

        <Button
          type="submit"
          size="sm"
          className="h-12 w-12 p-0 rounded-full bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white shadow-lg shadow-cyan-500/20"
          disabled={isLoading || (!text.trim() && !file)}
        >
          <Send className="h-5 w-5" />
        </Button>
      </div>
    </form>
  )
}
