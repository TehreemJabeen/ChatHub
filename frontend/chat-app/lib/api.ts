const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function generateToken(userId: string): Promise<string> {
    try {
        const res = await fetch(`${API_URL}/api/dev-generate-token?user_id=${userId}`);
        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${res.status}: Failed to generate token`);
        }
        const data = await res.json();
        return data.jwt;
    } catch (error: any) {
        if (error.message.includes('fetch')) {
            throw new Error(`Cannot connect to backend at ${API_URL}. Is the server running?`);
        }
        throw error;
    }
}

export async function fetchUserProfile(token: string) {
    const res = await fetch(`${API_URL}/api/users/me`, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });
    if (!res.ok) {
        throw new Error('Failed to fetch profile');
    }
    const profile = await res.json();
    console.log('[API] Fetched user profile:', profile);
    console.log('[API] Username:', profile.username);
    return profile;
}
