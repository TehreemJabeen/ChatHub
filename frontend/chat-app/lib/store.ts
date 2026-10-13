import { create } from 'zustand';
import { Chat, AvailableChat, Message, UserProfile } from './types';

interface AppState {
    currentUser: UserProfile | null;
    setCurrentUser: (user: UserProfile) => void;

    privateKey: CryptoKey | null;
    setPrivateKey: (key: CryptoKey | null) => void;

    chats: Chat[];
    setChats: (chats: Chat[]) => void;

    availableChats: AvailableChat[];
    setAvailableChats: (chats: AvailableChat[]) => void;

    activeChatId: number | null;
    setActiveChatId: (id: number | null) => void;

    messages: { [chatId: number]: Message[] };
    setMessages: (chatId: number, messages: Message[]) => void;
    addMessage: (chatId: number, message: Message) => void;
    removeChat: (chatId: number) => void;
    addAvailableChat: (chat: AvailableChat) => void;

    // Reset all state
    resetStore: () => void;
}

export const useAppStore = create<AppState>((set) => ({
    currentUser: null,
    setCurrentUser: (user) => set({ currentUser: user }),

    privateKey: null,
    setPrivateKey: (key) => set({ privateKey: key }),

    chats: [],
    setChats: (chats) => set({ chats }),

    availableChats: [],
    setAvailableChats: (chats) => set({ availableChats: chats }),

    activeChatId: null,
    setActiveChatId: (id) => set({ activeChatId: id }),

    messages: {},
    setMessages: (chatId, messages) =>
        set((state) => ({
            messages: { ...state.messages, [chatId]: messages },
        })),
    addMessage: (chatId, message) =>
        set((state) => ({
            messages: {
                ...state.messages,
                [chatId]: [...(state.messages[chatId] || []), message],
            },
        })),

    removeChat: (chatId) =>
        set((state) => {
            const newMessages = { ...state.messages };
            delete newMessages[chatId];
            return {
                chats: state.chats.filter(chat => chat.chat_id !== chatId),
                messages: newMessages,
                activeChatId: state.activeChatId === chatId ? null : state.activeChatId
            };
        }),

    addAvailableChat: (chat) =>
        set((state) => {
            // Don't add if already exists
            const exists = state.availableChats.some(c => c.chat_id === chat.chat_id);
            if (exists) return state;
            return {
                availableChats: [...state.availableChats, chat]
            };
        }),

    // Reset all state to initial values
    resetStore: () => set({
        currentUser: null,
        privateKey: null,
        chats: [],
        availableChats: [],
        activeChatId: null,
        messages: {}
    }),
}));
