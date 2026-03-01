const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/ws';

export const getWsUrl = () => import.meta.env.VITE_WS_URL || DEFAULT_WS_URL;

export const getApiBaseUrl = (wsUrl = getWsUrl()) =>
    wsUrl.replace('ws://', 'http://').replace('wss://', 'https://').replace('/ws', '');

export const buildApiUrl = (path: string, params?: URLSearchParams) => {
    const query = params?.toString();
    return `${getApiBaseUrl()}${path}${query ? `?${query}` : ''}`;
};
