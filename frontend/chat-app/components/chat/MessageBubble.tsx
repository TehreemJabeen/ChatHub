import { clsx } from "clsx"
import { format } from "date-fns"
import { Lock } from "lucide-react"

interface MessageBubbleProps {
  message: any
  isOwn: boolean
}

export function MessageBubble({ message, isOwn }: MessageBubbleProps) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

  return (
    <div className={clsx("flex w-full mb-4", isOwn ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "rounded-lg px-5 py-3 relative group shadow-lg",
          isOwn
            ? "bg-gradient-to-br from-cyan-600 to-cyan-500 text-white rounded-br-none shadow-cyan-500/20 max-w-2xl"
            : "bg-white/10 backdrop-blur-sm text-white/90 rounded-bl-none border border-cyan-400/20 shadow-black/20 max-w-2xl",
        )}
      >
        {!isOwn && <p className="text-xs text-white/60 mb-1.5 font-medium">{message.sender_username}</p>}

        {message.kind === "text" && (
          <p className="whitespace-pre-wrap break-words text-base leading-relaxed">
            {message.decryptedContent || "Decrypting..."}
          </p>
        )}

        {message.kind === "image" && (
          <div className="rounded-lg overflow-hidden my-2">
            <img
              src={message.file_url?.startsWith("http") ? message.file_url : `${API_URL}${message.file_url}`}
              alt="Shared image"
              className="max-w-full h-auto"
            />
          </div>
        )}

        {message.kind === "file" && (
          <a
            href={message.file_url?.startsWith("http") ? message.file_url : `${API_URL}${message.file_url}`}
            download={message.file_name}
            className="flex items-center gap-3 p-3 bg-black/20 rounded-md hover:bg-black/30 transition-colors cursor-pointer"
          >
            <div className="h-10 w-10 bg-white/10 rounded flex items-center justify-center">📄</div>
            <div className="overflow-hidden">
              <p className="text-base truncate">{message.file_name}</p>
              <p className="text-sm opacity-70">{formatBytes(message.file_size)}</p>
            </div>
          </a>
        )}

        <div className={clsx("flex items-center justify-end gap-1.5 mt-2", isOwn ? "text-cyan-200" : "text-white/40")}>
          <span className="text-xs">
            {message.created_at ? format(new Date(message.created_at), "HH:mm") : "Sending..."}
          </span>
          {message.is_encrypted && <Lock className="h-4 w-4" />}
        </div>
      </div>
    </div>
  )
}

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return "0 Bytes"
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${Number.parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}
