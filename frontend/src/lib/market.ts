export const normalizeSymbol = (raw?: string) => {
    if (!raw) return '';
    return raw
        .toUpperCase()
        .replace(/[-_]/g, '')
        .replace(/\//g, '')
        .replace(/\.PERP$/i, '');
};

export const formatTradingPair = (raw?: string) => {
    if (!raw) return 'N/A';
    const token = normalizeSymbol(raw);
    if (token.endsWith('USDT')) return `${token.slice(0, -4)}/USDT`;
    if (token.endsWith('USDC')) return `${token.slice(0, -4)}/USDC`;
    if (token.endsWith('USD')) return `${token.slice(0, -3)}/USD`;
    return token;
};
