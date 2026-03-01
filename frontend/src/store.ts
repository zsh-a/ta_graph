import { create } from 'zustand';
import { processDashboardEvent } from './store/eventProcessor';
import { MAX_LOGS, MAX_PRICES } from './store/types';
import type { CandlePoint, DashboardEvent, TradeLog } from './store/types';

interface TradingState {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    total_pnl: number;
    pnl_percentage: number;
    max_drawdown: number;
    drawdown_percent: number;
    current_position: any | null;
}

interface SafetyState {
    equity_protector: Record<string, unknown>;
    error_count: number;
    last_error: string | null;
}

interface DashboardState {
    status: string;
    system: any;
    trading: TradingState;
    performance: any;
    safety: SafetyState;
    logs: TradeLog[];
    candles: CandlePoint[];
    driftHistory: number[];
    analysis: {
        market_cycle: string;
        always_in_direction: string;
        setup_quality: number;
        drift_score: number;
        changed_fields: string[];
        buying_pressure_delta: number;
        selling_pressure_delta: number;
        validation_valid: boolean;
        warning_count: number;
        error_count: number;
    };
    market: {
        symbol: string;
        exchange: string;
        timeframe: string;
        current_price: number;
        price_change_24h: number;
    };

    updateFromInitialState: (data: any) => void;
    setSystemStatus: (status: string) => void;
    processEvent: (message: DashboardEvent, isHistory?: boolean) => Partial<DashboardState>;
}

const dedupeAndSortCandles = (rawCandles: CandlePoint[]) => {
    const sorted = [...rawCandles].sort((a, b) => a.time - b.time);
    const map = new Map<number, CandlePoint>();
    for (const candle of sorted) {
        const roundedTime = Math.round(candle.time);
        map.set(roundedTime, { ...candle, time: roundedTime });
    }
    return [...map.values()].slice(-MAX_PRICES);
};

const pushDriftScore = (history: number[], score: number) => {
    if (!Number.isFinite(score)) return history;
    return [...history, score].slice(-50);
};

export const useStore = create<DashboardState>((set, get) => ({
    status: 'offline',
    system: { heartbeat_count: 0, last_heartbeat: null },
    trading: {
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        total_pnl: 0,
        pnl_percentage: 0,
        max_drawdown: 0,
        drawdown_percent: 0,
        current_position: null
    },
    performance: { recent_pnl: [], execution_times: [] },
    safety: { equity_protector: {}, error_count: 0, last_error: null },
    logs: [],
    candles: [],
    driftHistory: [],
    analysis: {
        market_cycle: 'unknown',
        always_in_direction: 'neutral',
        setup_quality: 0,
        drift_score: 0,
        changed_fields: [],
        buying_pressure_delta: 0,
        selling_pressure_delta: 0,
        validation_valid: false,
        warning_count: 0,
        error_count: 0
    },
    market: {
        symbol: 'BTCUSDT',
        exchange: 'bitget',
        timeframe: '1h',
        current_price: 0,
        price_change_24h: 0
    },

    updateFromInitialState: (data) => set((state) => {
        let accumulatedLogs: TradeLog[] = [];
        let accumulatedCandles: CandlePoint[] = [];
        let replayStatus = data.system?.status || state.status;
        let replayDriftHistory = state.driftHistory;
        let replayAnalysis: DashboardState['analysis'] = state.analysis;
        let replayMarket: DashboardState['market'] = state.market;

        if (Array.isArray(data.history)) {
            for (const event of data.history) {
                const { updates } = processDashboardEvent({
                    message: event,
                    isHistory: true,
                    currentTrading: state.trading,
                    currentLogs: accumulatedLogs
                });

                if (updates.logs) {
                    accumulatedLogs = [...updates.logs, ...accumulatedLogs];
                }
                if (updates.candles) {
                    accumulatedCandles = [...accumulatedCandles, ...updates.candles];
                }
                if (updates.status !== undefined) {
                    replayStatus = updates.status;
                }
                if (updates.analysis !== undefined) {
                    if (Number.isFinite(updates.analysis.drift_score)) {
                        replayDriftHistory = pushDriftScore(replayDriftHistory, Number(updates.analysis.drift_score));
                    }
                    replayAnalysis = {
                        market_cycle: updates.analysis.market_cycle ?? replayAnalysis.market_cycle,
                        always_in_direction: updates.analysis.always_in_direction ?? replayAnalysis.always_in_direction,
                        setup_quality: updates.analysis.setup_quality ?? replayAnalysis.setup_quality,
                        drift_score: updates.analysis.drift_score ?? replayAnalysis.drift_score,
                        changed_fields: updates.analysis.changed_fields ?? replayAnalysis.changed_fields,
                        buying_pressure_delta: updates.analysis.buying_pressure_delta ?? replayAnalysis.buying_pressure_delta,
                        selling_pressure_delta: updates.analysis.selling_pressure_delta ?? replayAnalysis.selling_pressure_delta,
                        validation_valid: updates.analysis.validation_valid ?? replayAnalysis.validation_valid,
                        warning_count: updates.analysis.warning_count ?? replayAnalysis.warning_count,
                        error_count: updates.analysis.error_count ?? replayAnalysis.error_count,
                    };
                }
                if (updates.market !== undefined) {
                    replayMarket = {
                        symbol: updates.market.symbol ?? replayMarket.symbol,
                        exchange: updates.market.exchange ?? replayMarket.exchange,
                        timeframe: updates.market.timeframe ?? replayMarket.timeframe,
                        current_price: updates.market.current_price ?? replayMarket.current_price,
                        price_change_24h: updates.market.price_change_24h ?? replayMarket.price_change_24h,
                    };
                }
            }
        }

        return {
            ...state,
            status: replayStatus,
            system: data.system || state.system,
            trading: data.trading || state.trading,
            performance: data.performance || state.performance,
            safety: data.safety || state.safety,
            logs: accumulatedLogs.slice(0, MAX_LOGS),
            candles: dedupeAndSortCandles(accumulatedCandles),
            driftHistory: replayDriftHistory,
            analysis: replayAnalysis,
            market: replayMarket
        };
    }),

    processEvent: (message, isHistory = false) => {
        const state = get();
        const { updates } = processDashboardEvent({
            message,
            isHistory,
            currentTrading: state.trading,
            currentLogs: state.logs
        });

        const normalizedUpdates: Partial<DashboardState> = {
            ...updates,
            driftHistory: updates.analysis && Number.isFinite(updates.analysis.drift_score)
                ? pushDriftScore(state.driftHistory, Number(updates.analysis.drift_score))
                : undefined,
            analysis: updates.analysis
                ? {
                    market_cycle: updates.analysis.market_cycle ?? state.analysis.market_cycle,
                    always_in_direction: updates.analysis.always_in_direction ?? state.analysis.always_in_direction,
                    setup_quality: updates.analysis.setup_quality ?? state.analysis.setup_quality,
                    drift_score: updates.analysis.drift_score ?? state.analysis.drift_score,
                    changed_fields: updates.analysis.changed_fields ?? state.analysis.changed_fields,
                    buying_pressure_delta: updates.analysis.buying_pressure_delta ?? state.analysis.buying_pressure_delta,
                    selling_pressure_delta: updates.analysis.selling_pressure_delta ?? state.analysis.selling_pressure_delta,
                    validation_valid: updates.analysis.validation_valid ?? state.analysis.validation_valid,
                    warning_count: updates.analysis.warning_count ?? state.analysis.warning_count,
                    error_count: updates.analysis.error_count ?? state.analysis.error_count,
                }
                : undefined,
            market: updates.market
                ? {
                    symbol: updates.market.symbol ?? state.market.symbol,
                    exchange: updates.market.exchange ?? state.market.exchange,
                    timeframe: updates.market.timeframe ?? state.market.timeframe,
                    current_price: updates.market.current_price ?? state.market.current_price,
                    price_change_24h: updates.market.price_change_24h ?? state.market.price_change_24h,
                }
                : undefined,
        };

        if (!isHistory) {
            set((prev) => ({ ...prev, ...normalizedUpdates }));
        }

        return normalizedUpdates;
    },
    setSystemStatus: (status) => set({ status }),
}));
