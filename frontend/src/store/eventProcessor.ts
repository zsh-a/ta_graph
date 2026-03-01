import {
    createLogId,
    MAX_LOGS,
    MAX_PRICES,
} from './types';
import type { CandlePoint, EventProcessInput, EventProcessOutput, TradeLog } from './types';
import { normalizeSymbol } from '../lib/market';

const withTimestamp = (timestamp?: string) => timestamp || new Date().toISOString();

const buildLog = (payload: Omit<TradeLog, 'id'>): TradeLog => ({
    id: createLogId(),
    ...payload
});

const toText = (value: unknown, maxLen = 1600): string => {
    if (typeof value !== 'string') return '';
    const normalized = value.replace(/\s+\n/g, '\n').trim();
    if (!normalized) return '';
    return normalized.length > maxLen ? `${normalized.slice(0, maxLen)}...` : normalized;
};

const normalizeCandles = (ohlcv: any[]): CandlePoint[] => {
    if (!Array.isArray(ohlcv)) return [];
    return ohlcv
        .filter((row) => Array.isArray(row) && row.length >= 5)
        .map((row) => ({
            time: Math.round(Number(row[0]) / 1000),
            open: Number(row[1]),
            high: Number(row[2]),
            low: Number(row[3]),
            close: Number(row[4]),
            volume: Number(row[5] ?? 0),
        }))
        .filter((c) => Number.isFinite(c.time) && Number.isFinite(c.close));
};

export const processDashboardEvent = ({
    message,
    isHistory,
    currentTrading,
    currentLogs
}: EventProcessInput): EventProcessOutput => {
    const { type, data = {}, timestamp } = message;
    const eventTs = withTimestamp(timestamp);
    const updates: EventProcessOutput['updates'] = {};
    const eventLogs: TradeLog[] = [];

    switch (type) {
        case 'initial_state':
            break;

        case 'node_start':
            break;

        case 'ai_thinking':
            break;

        case 'analysis_complete':
            updates.analysis = {
                market_cycle: data.analysis?.market_cycle,
                always_in_direction: data.analysis?.always_in_direction,
                setup_quality: data.analysis?.setup_quality,
                drift_score: data.analysis?._validation?.phase_consistency?.drift_score,
                changed_fields: Array.isArray(data.analysis?._validation?.phase_consistency?.changed_fields)
                    ? data.analysis._validation.phase_consistency.changed_fields
                    : [],
                buying_pressure_delta: data.analysis?._validation?.phase_consistency?.buying_pressure_delta,
                selling_pressure_delta: data.analysis?._validation?.phase_consistency?.selling_pressure_delta,
                validation_valid: data.analysis?._validation?.valid,
                warning_count: Array.isArray(data.analysis?._validation?.warnings) ? data.analysis._validation.warnings.length : 0,
                error_count: Array.isArray(data.analysis?._validation?.errors) ? data.analysis._validation.errors.length : 0,
            };
            eventLogs.push(buildLog({
                type: 'success',
                node: data.node,
                message: `Analysis complete: ${data.analysis?.market_cycle}`,
                timestamp: eventTs,
                data: data.analysis
            }));
            break;

        case 'strategy_complete':
            eventLogs.push(buildLog({
                type: 'decision',
                node: data.node,
                message: `Decision: ${data.decision?.operation || 'Hold'}`,
                timestamp: eventTs,
                data: data.decision
            }));
            break;

        case 'market_data_complete':
            updates.market = {
                symbol: normalizeSymbol(data.symbol),
                exchange: data.exchange,
                timeframe: data.timeframe,
                current_price: data.current_price,
                price_change_24h: data.price_change_24h
            };
            if (Array.isArray(data.ohlcv)) {
                updates.candles = normalizeCandles(data.ohlcv).slice(-MAX_PRICES);
            }
            eventLogs.push(buildLog({
                type: 'market_data',
                node: data.node,
                message: 'Market data fetched successfully',
                timestamp: eventTs,
                data
            }));
            break;

        case 'risk_assessment_complete': {
            const plans = Array.isArray(data.execution_plans) ? data.execution_plans : [];
            const approvedPlans = plans.filter((p: any) => p?.status === 'APPROVED');
            const bestPlan = approvedPlans[0];

            if (bestPlan) {
                eventLogs.push(buildLog({
                    type: 'plan',
                    node: 'risk',
                    message: `Risk Plan: ${bestPlan.operation} ${bestPlan.symbol}`,
                    timestamp: eventTs,
                    data: bestPlan
                }));
            }

            if (data.summary) {
                eventLogs.push(buildLog({
                    type: 'risk_summary',
                    node: 'risk',
                    message: `Risk Summary: ${approvedPlans.length} approved / ${plans.length} reviewed`,
                    timestamp: eventTs,
                    data: data.summary
                }));
            }
            break;
        }

        case 'status_change':
            updates.status = data.status;
            break;

        case 'position_update':
            updates.trading = { ...currentTrading, current_position: data };
            break;

        case 'error_added':
            eventLogs.push(buildLog({
                type: 'error',
                node: 'system',
                message: data.error,
                timestamp: eventTs
            }));
            break;

        case 'trade_update':
            eventLogs.push(buildLog({
                type: 'trade',
                node: 'execution',
                message: `New trade recorded. PnL: ${data.pnl}`,
                timestamp: eventTs,
                data
            }));
            break;

        case 'market_update':
            updates.market = {
                symbol: normalizeSymbol(data.symbol),
                timeframe: data.timeframe,
                current_price: data.price
            };
            break;

        case 'execution_complete':
            eventLogs.push(buildLog({
                type: 'execution',
                node: data.node,
                message: `Execution: ${data.trade?.side} ${data.trade?.symbol} ${data.trade?.status}`,
                timestamp: eventTs,
                data: data.trade
            }));
            break;

        case 'llm_log':
            eventLogs.push(buildLog({
                type: 'llm_log',
                node: data.node || 'llm',
                message: `LLM output (${data.model || 'unknown model'})`,
                timestamp: eventTs,
                data: {
                    model: data.model || 'unknown',
                    prompt: toText(data.prompt, 800),
                    reasoning: toText(data.reasoning, 1600),
                    response: toText(data.response, 2400),
                }
            }));
            break;

        case 'order_monitor_update':
            eventLogs.push(buildLog({
                type: 'monitor',
                node: data.node,
                message: `Order Monitor: ${data.status} ${data.order_id}`,
                timestamp: eventTs,
                data
            }));
            break;

        case 'l0_gate':
            eventLogs.push(buildLog({
                type: data.is_dead_market ? 'warning' : 'info',
                node: data.node || 'l0_gate',
                message: data.is_dead_market
                    ? 'L0 Gate: market inactive, analysis skipped'
                    : 'L0 Gate: market active',
                timestamp: eventTs,
                data
            }));
            break;

        case 'l0_preprocessing_complete':
            eventLogs.push(buildLog({
                type: data.is_dead_market ? 'warning' : 'success',
                node: data.node || 'market_data',
                message: data.is_dead_market
                    ? `L0 Preprocess: inactive (ATR ${data.atr_pct?.toFixed(2)}%)`
                    : `L0 Preprocess: active (ATR ${data.atr_pct?.toFixed(2)}%)`,
                timestamp: eventTs,
                data
            }));
            break;

        case 'node_complete':
            break;
    }

    if (eventLogs.length > 0) {
        updates.logs = isHistory ? eventLogs : [...eventLogs, ...currentLogs].slice(0, MAX_LOGS);
    }

    return { updates };
};
