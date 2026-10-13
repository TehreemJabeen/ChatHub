"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Loader2, Lock, Zap } from "lucide-react"
import { Button, Input } from "@/components/ui/common"
import { generateToken, fetchUserProfile } from "@/lib/api"
import { generateKeyPair, storeKeyPair, getKeyPair, exportPublicKey } from "@/lib/crypto"
import { connectSocket, socket } from "@/lib/socket"
import { useAppStore } from "@/lib/store"

export default function ConnectPage() {
  const [userId, setUserId] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState("")
  const router = useRouter()
  const { setCurrentUser, setPrivateKey } = useAppStore()

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!userId.trim()) return

    setIsLoading(true)
    setStatus("Authenticating...")

    try {
      const token = await generateToken(userId)
      setStatus("Checking encryption keys...")
      let keyPair = await getKeyPair()

      if (!keyPair) {
        setStatus("Generating new RSA key pair...")
        keyPair = await generateKeyPair()
        await storeKeyPair(keyPair)
      }

      setPrivateKey(keyPair.privateKey)
      setStatus("Connecting to server...")
      connectSocket(token)

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error("Connection timeout")), 10000)

        const onConnect = () => {
          clearTimeout(timeout)
          socket.off("connect", onConnect)
          socket.off("connect_error", onError)
          resolve()
        }

        const onError = (err: any) => {
          clearTimeout(timeout)
          socket.off("connect", onConnect)
          socket.off("connect_error", onError)
          reject(err)
        }

        if (socket.connected) {
          onConnect()
        } else {
          socket.on("connect", onConnect)
          socket.on("connect_error", onError)
        }
      })

      const profile = await fetchUserProfile(token)
      setCurrentUser(profile)

      if (!profile.public_key) {
        setStatus("Uploading public key...")
        const publicKeyPem = await exportPublicKey(keyPair.publicKey)
        await new Promise<void>((resolve) => {
          socket.emit("upload_public_key", { public_key: publicKeyPem })
          socket.once("public_key_uploaded", () => resolve())
          setTimeout(() => resolve(), 2000)
        })
      }

      setStatus("Connected!")
      setTimeout(() => router.push("/chat"), 500)
    } catch (error: any) {
      setStatus(`Error: ${error.message || "Connection failed"}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="relative">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-cyan-500/15 to-cyan-400/10 blur-xl" />
          <div className="relative glass rounded-2xl p-8">
            <div className="text-center mb-8">
              <div className="flex justify-center mb-4">
                <div className="h-16 w-16 rounded-xl bg-gradient-to-br from-cyan-500/20 to-cyan-400/10 flex items-center justify-center border border-cyan-400/30 shadow-lg shadow-cyan-500/10">
                  <Lock className="h-8 w-8 text-cyan-300" />
                </div>
              </div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-300 to-cyan-200 bg-clip-text text-transparent mb-2">
                Secure Chat
              </h1>
              <p className="text-white/50 text-sm">End-to-end encrypted messaging</p>
            </div>

            <form onSubmit={handleConnect} className="space-y-5">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white/70 uppercase tracking-wide">User ID</label>
                <Input
                  type="text"
                  placeholder="Enter your UUID"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  disabled={isLoading}
                  className="bg-white/5 border-cyan-400/20 text-white placeholder-white/30 focus:border-cyan-400/50 focus:ring-cyan-400/20"
                />
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full h-10 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-medium shadow-lg shadow-cyan-500/20"
                size="lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">{status}</span>
                  </>
                ) : (
                  <>
                    <Zap className="h-4 w-4" />
                    <span>Connect</span>
                  </>
                )}
              </Button>
            </form>

            {status && !isLoading && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center text-red-400 text-xs mt-4"
              >
                {status}
              </motion.p>
            )}

            <div className="text-center text-xs text-white/40 mt-8 space-y-1">
              <p>🔒 End-to-End Encryption</p>
              <p>🔑 Keys Never Leave Your Device</p>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
