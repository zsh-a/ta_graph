import { useEffect, useRef } from 'react';
import { useStore } from '../store';

export const useWebSocket = (url: string) => {
    const socketRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectAttemptRef = useRef(0);
    const updateFromInitialState = useStore((state) => state.updateFromInitialState);
    const setSystemStatus = useStore((state) => state.setSystemStatus);
    const processEvent = useStore((state) => state.processEvent);

    useEffect(() => {
        let isMounted = true;

        const connect = () => {
            if (!isMounted) return;

            const socket = new WebSocket(url);
            socketRef.current = socket;

            socket.onopen = () => {
                if (!isMounted) {
                    socket.close();
                    return;
                }
                reconnectAttemptRef.current = 0;
                console.log('Connected to Dashboard WS');
                setSystemStatus('online');
            };

            socket.onmessage = (event) => {
                if (!isMounted) return;
                let message: any;
                try {
                    message = JSON.parse(event.data);
                } catch (parseError) {
                    console.error('Invalid WS payload:', parseError);
                    return;
                }

                if (message.type === 'initial_state') {
                    updateFromInitialState(message.data);
                } else {
                    processEvent(message);
                }
            };

            socket.onclose = () => {
                if (isMounted) {
                    console.log('Disconnected from Dashboard WS');
                    setSystemStatus('offline');
                    reconnectAttemptRef.current += 1;
                    const baseDelay = Math.min(30000, 1000 * (2 ** reconnectAttemptRef.current));
                    const jitter = Math.floor(Math.random() * 500);
                    const retryDelay = baseDelay + jitter;
                    reconnectTimerRef.current = setTimeout(connect, retryDelay);
                }
            };

            socket.onerror = (err) => {
                console.error('WS Error:', err);
                socket.close();
            };
        };

        connect();

        return () => {
            isMounted = false;
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [url]);

    return {};
};
