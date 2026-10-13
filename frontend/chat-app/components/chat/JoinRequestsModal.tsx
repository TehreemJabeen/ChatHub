import { useEffect, useState } from 'react';
import { socket } from '@/lib/socket';
import { Button } from '@/components/ui/common';
import { X, Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface JoinRequest {
    request_id: number;
    user_id: string;
    username: string;
    full_name: string;
    requested_at: string;
}

interface JoinRequestsModalProps {
    chatId: number;
    isOpen: boolean;
    onClose: () => void;
}

export function JoinRequestsModal({ chatId, isOpen, onClose }: JoinRequestsModalProps) {
    const [requests, setRequests] = useState<JoinRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [processingId, setProcessingId] = useState<number | null>(null);

    useEffect(() => {
        if (!isOpen) return;

        setIsLoading(true);
        socket.emit('get_pending_requests', { chat_id: chatId });

        const handleRequestsList = (data: { requests: JoinRequest[] }) => {
            setRequests(data.requests);
            setIsLoading(false);
        };

        const handleNewRequest = (data: JoinRequest & { chat_id: number }) => {
            if (data.chat_id === chatId) {
                setRequests(prev => [...prev, data]);
            }
        };

        const handleRequestProcessed = (data: { request_id: number; status: string }) => {
            setRequests(prev => prev.filter(req => req.request_id !== data.request_id));
            setProcessingId(null);
        };

        const handleError = (error: { error: string }) => {
            console.error('Pending requests error:', error);
            setIsLoading(false);
            // Optionally show error to user
        };

        socket.on('pending_requests', handleRequestsList);
        socket.on('new_join_request', handleNewRequest);
        socket.on('join_request_approved', handleRequestProcessed);
        socket.on('join_request_rejected', handleRequestProcessed);
        socket.on('pending_requests_error', handleError);

        return () => {
            socket.off('pending_requests', handleRequestsList);
            socket.off('new_join_request', handleNewRequest);
            socket.off('join_request_approved', handleRequestProcessed);
            socket.off('join_request_rejected', handleRequestProcessed);
            socket.off('pending_requests_error', handleError);
        };
    }, [chatId, isOpen]);

    const handleProcess = (requestId: number, action: 'approve' | 'reject') => {
        setProcessingId(requestId);
        socket.emit('process_join_request', {
            request_id: requestId,
            action: action
        });
    };

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}
        >
            <div
                className="w-full max-w-md bg-zinc-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden"
                style={{ margin: 'auto' }}
            >
                <div className="p-4 border-b border-white/10 flex items-center justify-between bg-zinc-950/50">
                    <h3 className="font-semibold text-white">Join Requests</h3>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                <div className="p-4 max-h-[60vh] overflow-y-auto">
                    {isLoading ? (
                        <div className="flex justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
                        </div>
                    ) : requests.length === 0 ? (
                        <div className="text-center py-8 text-white/50">
                            No pending requests
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {requests.map((req) => (
                                <div key={req.request_id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5">
                                    <div>
                                        <p className="font-medium text-white">{req.full_name}</p>
                                        <p className="text-sm text-white/50">@{req.username}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            size="icon"
                                            className="h-8 w-8 bg-green-500/20 text-green-400 hover:bg-green-500/30"
                                            onClick={() => handleProcess(req.request_id, 'approve')}
                                            disabled={processingId === req.request_id}
                                        >
                                            {processingId === req.request_id ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <Check className="h-4 w-4" />
                                            )}
                                        </Button>
                                        <Button
                                            size="icon"
                                            className="h-8 w-8 bg-red-500/20 text-red-400 hover:bg-red-500/30"
                                            onClick={() => handleProcess(req.request_id, 'reject')}
                                            disabled={processingId === req.request_id}
                                        >
                                            {processingId === req.request_id ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <X className="h-4 w-4" />
                                            )}
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
