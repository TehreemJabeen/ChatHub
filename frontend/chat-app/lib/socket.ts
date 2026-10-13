import { io } from 'socket.io-client';
import { useAppStore } from './store';

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || 'http://localhost:8000';

// Connect to /chat namespace (backend uses this namespace)
export const socket = io(`${SOCKET_URL}/chat`, {
    path: '/socket.io',
    autoConnect: false,
    reconnection: false,
    transports: ['websocket', 'polling']
});

// Global listener - always active, stores chats immediately when received
socket.on('load_chats', (data) => {
    console.log('[SOCKET] Global load_chats received:', data);
    console.log('[SOCKET] Member chats:', data.member_chats?.length || 0);
    console.log('[SOCKET] Available chats:', data.available_chats?.length || 0);

    const store = useAppStore.getState();
    store.setChats(data.member_chats || []);
    store.setAvailableChats(data.available_chats || []);
});

export function connectSocket(token: string) {
    socket.auth = { token };
    socket.connect();
}
