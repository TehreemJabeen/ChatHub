export default function ChatPage() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-white/50 space-y-4">
      <div className="h-20 w-20 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center border border-blue-400/20">
        <span className="text-4xl">💬</span>
      </div>
      <h2 className="text-xl font-semibold text-white/70">Welcome to Secure Chat</h2>
      <p className="max-w-sm text-center text-sm text-white/50">
        Select a conversation or create a new one to start messaging securely.
      </p>
    </div>
  )
}
