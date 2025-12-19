import { useEffect, useRef } from 'react';
import { useStore } from '../store';

export const useWebSocket = (url: string) => {
    const socketRef = useRef<WebSocket | null>(null);
    const {
        updateFromInitialState,
        setSystemStatus,
        processEvent
    } = useStore();

    useEffect(() => {
        let isMounted = true;
        let reconnectTimeout: ReturnType<typeof setTimeout>;

        const connect = () => {
            if (!isMounted) return;

            const socket = new WebSocket(url);
            socketRef.current = socket;

            socket.onopen = () => {
                if (!isMounted) {
                    socket.close();
                    return;
                }
                console.log('Connected to Dashboard WS');
                setSystemStatus('online');
            };

            socket.onmessage = (event) => {
                if (!isMounted) return;
                const message = JSON.parse(event.data);

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
                    // Reconnect after 3 seconds
                    reconnectTimeout = setTimeout(connect, 3000);
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
            clearTimeout(reconnectTimeout);
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [url]);

    const sendCommand = (type: string, data: any) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ type, data }));
        }
    };

    return { sendCommand };
};
