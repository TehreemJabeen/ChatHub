export interface Chat {
    chat_id: number;
    name: string;
    is_group: boolean;
    is_locked: boolean;
    is_admin: boolean;
    // created_by is NOT returned for member chats in load_chats
}

export interface AvailableChat {
    chat_id: number;
    name: string;
    is_locked: boolean;
    created_by: string; // UUID string
}

export interface Message {
    id: number;
    chat_id: number;
    sender_id: string; // UUID string
    sender_username: string;
    sender_full_name?: string;
    kind: 'text' | 'image' | 'file';
    ciphertext: string;
    iv: string;
    is_encrypted: boolean;
    created_at: string;
    file_url?: string;
    file_name?: string;
    file_size?: number;
    file_type?: string;
    decryptedContent?: string;
    is_own?: boolean;
}

export interface UserProfile {
    user_id: string; // UUID string
    username: string;
    full_name: string;
    email: string;
    public_key: string;
}
