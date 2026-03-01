export const MAX_LOGS = 500;
export const MAX_PRICES = 1000;

export type PricePoint = {
    time: number;
    value: number;
};

export interface TradeLog {
    id: string;
    type: string;
    node: string;
    message: string;
    timestamp: string;
    data?: unknown;
}

export interface DashboardEvent<T = any> {
    type: string;
    data: T;
    timestamp?: string;
}

export interface EventProcessInput {
    message: DashboardEvent;
    isHistory: boolean;
    currentTrading: any;
    currentPrices: PricePoint[];
    currentLogs: TradeLog[];
}

export interface EventProcessOutput {
    updates: {
        status?: string;
        trading?: any;
        activeNode?: string | null;
        prices?: PricePoint[];
        logs?: TradeLog[];
    };
}

export const createLogId = () => Math.random().toString(36).slice(2, 11);
