export const MAX_LOGS = 300;
export const MAX_PRICES = 2000;

export type CandlePoint = {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
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
    currentLogs: TradeLog[];
}

export interface EventProcessOutput {
    updates: {
        status?: string;
        trading?: any;
        candles?: CandlePoint[];
        analysis?: {
            market_cycle?: string;
            always_in_direction?: string;
            setup_quality?: number;
            drift_score?: number;
            changed_fields?: string[];
            buying_pressure_delta?: number;
            selling_pressure_delta?: number;
            validation_valid?: boolean;
            warning_count?: number;
            error_count?: number;
        };
        market?: {
            symbol?: string;
            exchange?: string;
            timeframe?: string;
            current_price?: number;
            price_change_24h?: number;
        };
        logs?: TradeLog[];
    };
}

export const createLogId = () => Math.random().toString(36).slice(2, 11);
