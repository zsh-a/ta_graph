import {
    createLogId,
    MAX_LOGS,
    MAX_PRICES,
} from './types';
import type { EventProcessInput, EventProcessOutput, PricePoint, TradeLog } from './types';

const withTimestamp = (timestamp?: string) => timestamp || new Date().toISOString();

const buildLog = (payload: Omit<TradeLog, 'id'>): TradeLog => ({
    id: createLogId(),
    ...payload
});

const summarizeLlmLog = (data: any): string => {
    const model = data?.model || 'LLM';
    const node = data?.node || 'unknown';
    const reasoning = typeof data?.reasoning === 'string' ? data.reasoning.trim() : '';
    if (reasoning) {
        return `[${node}] ${model}: ${reasoning.slice(0, 160)}`;
    }
    return `[${node}] ${model}: response received`;
};

const normalizePricePoint = (timestamp: string | undefined, rawPrice: number): PricePoint => {
    const parsedTime = timestamp ? new Date(timestamp).getTime() / 1000 : Date.now() / 1000;
    const roundedTime = Math.round(parsedTime * 1000) / 1000;
    return { time: roundedTime, value: rawPrice };
};

export const processDashboardEvent = ({
    message,
    isHistory,
    currentTrading,
    currentPrices,
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
            updates.activeNode = data.node;
            break;

        case 'ai_thinking':
            break;

        case 'analysis_complete':
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
            if (typeof data.price === 'number') {
                const price = normalizePricePoint(timestamp, data.price);

                if (isHistory) {
                    updates.prices = [price];
                } else {
                    const lastPrice = currentPrices[currentPrices.length - 1];
                    if (!lastPrice || price.time > lastPrice.time) {
                        updates.prices = [...currentPrices, price].slice(-MAX_PRICES);
                    } else if (price.time === lastPrice.time) {
                        updates.prices = [...currentPrices.slice(0, -1), price];
                    }
                }
            }
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
                node: data.node,
                message: summarizeLlmLog(data),
                timestamp: eventTs,
                data: {
                    model: data.model,
                    node: data.node,
                    reasoning: data.reasoning,
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
