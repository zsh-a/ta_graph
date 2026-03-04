import { useEffect, useMemo, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useStore } from '../store';
import { formatTradingPair } from '../lib/market';

export const PriceChart = () => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
    const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
    const entryLineRef = useRef<any>(null);
    const stopLineRef = useRef<any>(null);
    const takeProfitLineRef = useRef<any>(null);
    const candles = useStore((state) => state.candles);
    const market = useStore((state) => state.market);
    const position = useStore((state) => state.trading.current_position);
    const [range, setRange] = useState<'120' | '360' | '720' | '1200' | '2000' | 'all'>('720');
    const [hoverCandle, setHoverCandle] = useState<any | null>(null);

    const displayCandles = useMemo(() => candles, [candles]);

    const volumeData = useMemo(() => {
        return displayCandles.map((candle) => ({
            time: candle.time,
            value: candle.volume ?? 0,
            color: candle.close >= candle.open ? 'rgba(16,185,129,0.35)' : 'rgba(239,68,68,0.35)',
        }));
    }, [displayCandles]);

    const latestCandle = displayCandles.length > 0 ? displayCandles[displayCandles.length - 1] : null;
    const infoCandle = hoverCandle || latestCandle;

    const ema20Data = useMemo(() => {
        const alpha = 2 / (20 + 1);
        let ema = 0;
        return displayCandles.map((candle, idx) => {
            ema = idx === 0 ? candle.close : candle.close * alpha + ema * (1 - alpha);
            return { time: candle.time, value: Number(ema.toFixed(2)) };
        });
    }, [displayCandles]);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#cbd5e1',
            },
            grid: {
                vertLines: { color: '#1f2937' },
                horzLines: { color: '#1f2937' },
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight || 460,
            timeScale: {
                borderColor: '#273244',
                timeVisible: true,
                secondsVisible: false,
            },
            rightPriceScale: {
                borderColor: '#273244',
            },
            crosshair: {
                vertLine: { labelBackgroundColor: '#0ea5e9' },
                horzLine: { labelBackgroundColor: '#0ea5e9' },
            },
        });

        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        chartRef.current = chart;
        candleSeriesRef.current = series as ISeriesApi<"Candlestick">;

        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        chart.priceScale('volume').applyOptions({
            scaleMargins: {
                top: 0.78,
                bottom: 0,
            },
            borderVisible: false,
        });
        volumeSeriesRef.current = volumeSeries as ISeriesApi<"Histogram">;

        const emaSeries = chart.addSeries(LineSeries, {
            color: '#38bdf8',
            lineWidth: 2,
            title: 'EMA20',
            lastValueVisible: true,
            crosshairMarkerVisible: true,
        });
        emaSeriesRef.current = emaSeries as ISeriesApi<"Line">;

        const onCrosshairMove = (param: any) => {
            if (!param?.time || !candleSeriesRef.current) {
                setHoverCandle(null);
                return;
            }
            const candlePoint = param.seriesData?.get?.(candleSeriesRef.current as any);
            if (candlePoint) {
                setHoverCandle({
                    time: Number(param.time),
                    open: Number(candlePoint.open),
                    high: Number(candlePoint.high),
                    low: Number(candlePoint.low),
                    close: Number(candlePoint.close),
                });
            } else {
                setHoverCandle(null);
            }
        };
        chart.subscribeCrosshairMove(onCrosshairMove);

        let animationFrameId: number;

        const resizeObserver = new ResizeObserver((entries) => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const newRect = entries[0].contentRect;

            // Debounce resize via requestAnimationFrame
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            animationFrameId = requestAnimationFrame(() => {
                // Check if dimensions actually changed to avoid infinite loops
                if (chartContainerRef.current) {
                    chart.applyOptions({
                        width: newRect.width,
                        height: newRect.height
                    });
                }
            });
        });

        if (chartContainerRef.current) {
            resizeObserver.observe(chartContainerRef.current);
        }

        return () => {
            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            if (chartContainerRef.current) {
                resizeObserver.unobserve(chartContainerRef.current);
            }
            resizeObserver.disconnect();
            chart.unsubscribeCrosshairMove(onCrosshairMove);
            chart.remove();
        };
    }, []);

    const logs = useStore((state) => state.logs);

    useEffect(() => {
        if (candleSeriesRef.current && displayCandles.length > 0) {
            candleSeriesRef.current.setData(displayCandles as any);

            // Generate Marks from Execution Logs
            const executionMarkers = logs
                .filter(log => log.type === 'execution' && log.node === 'execution')
                .map(log => {
                    const trade = log.data as any;
                    // Validate we have a price and it's either FILLED or CLOSED
                    if (!trade || !trade.price || (trade.status !== 'FILLED' && trade.status !== 'CLOSED')) return null;

                    // Match log timestamp to candle time. 
                    // Note: LightweightCharts 'time' is usually seconds for dates or business days.
                    // The backend event provides an ISO string timestamp.
                    const eventTime = new Date(log.timestamp).getTime() / 1000;

                    // Find the closest candle or just use the exact time
                    let logTime = Math.round(eventTime);

                    const isBuy = trade.side.toLowerCase() === 'buy' || trade.side.toLowerCase() === 'long';
                    return {
                        time: logTime,
                        position: isBuy ? 'belowBar' : 'aboveBar',
                        color: isBuy ? '#10b981' : '#ef4444',
                        shape: isBuy ? 'arrowUp' : 'arrowDown',
                        text: `${trade.side.toUpperCase()} @ ${trade.price}`,
                    };
                })
                .filter(Boolean); // Remove nulls

            if (executionMarkers.length > 0) {
                // Must sort markers by time ascending as required by lightweight-charts
                executionMarkers.sort((a: any, b: any) => a.time - b.time);
                // Type safety constraint: Lightweight Charts requires unique time indices
                // deduplicate identical timestamp markers by slightly shifting them if needed, or taking the latest
                const uniqueMarkers = [];
                const timeMap = new Set();
                for (const m of executionMarkers) {
                    if (!timeMap.has(m!.time)) {
                        timeMap.add(m!.time);
                        uniqueMarkers.push(m);
                    }
                }

                try {
                    if (!(candleSeriesRef.current as any)._markersPlugin) {
                        (candleSeriesRef.current as any)._markersPlugin = createSeriesMarkers(
                            candleSeriesRef.current as any,
                            uniqueMarkers as any[]
                        );
                    } else {
                        (candleSeriesRef.current as any)._markersPlugin.setMarkers(uniqueMarkers as any[]);
                    }
                } catch (e) {
                    console.error("Failed to set markers:", e);
                }
            } else {
                if ((candleSeriesRef.current as any)._markersPlugin) {
                    (candleSeriesRef.current as any)._markersPlugin.setMarkers([]);
                }
            }

            if (volumeSeriesRef.current) {
                volumeSeriesRef.current.setData(volumeData as any);
            }
            if (emaSeriesRef.current) {
                emaSeriesRef.current.setData(ema20Data as any);
            }
            const chart = chartRef.current;
            if (!chart) return;

            if (range === 'all') {
                chart.timeScale().fitContent();
                return;
            }

            const lookback = Number(range);
            const to = displayCandles.length - 1;
            const from = Math.max(0, to - lookback);
            chart.timeScale().setVisibleLogicalRange({ from, to });
        }
    }, [displayCandles, volumeData, ema20Data, range, logs]);

    useEffect(() => {
        if (!candleSeriesRef.current) return;

        const series = candleSeriesRef.current;
        if (entryLineRef.current) {
            series.removePriceLine(entryLineRef.current);
            entryLineRef.current = null;
        }
        if (stopLineRef.current) {
            series.removePriceLine(stopLineRef.current);
            stopLineRef.current = null;
        }
        if (takeProfitLineRef.current) {
            series.removePriceLine(takeProfitLineRef.current);
            takeProfitLineRef.current = null;
        }

        const entry = Number((position as any)?.entry_price);
        const stop = Number((position as any)?.stop_loss ?? (position as any)?.stopLoss);
        const tp = Number((position as any)?.take_profit ?? (position as any)?.takeProfit);

        if (Number.isFinite(entry) && entry > 0) {
            entryLineRef.current = series.createPriceLine({
                price: entry,
                color: '#f59e0b',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'Entry',
            });
        }
        if (Number.isFinite(stop) && stop > 0) {
            stopLineRef.current = series.createPriceLine({
                price: stop,
                color: '#ef4444',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'SL',
            });
        }
        if (Number.isFinite(tp) && tp > 0) {
            takeProfitLineRef.current = series.createPriceLine({
                price: tp,
                color: '#10b981',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'TP',
            });
        }
    }, [position]);

    return (
        <div className="flex-1 glass-card p-4 flex flex-col min-h-0 border-primary/10">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                    <div className="w-2 h-4 bg-primary rounded-sm" />
                    Market Visualization ({formatTradingPair(market.symbol)})
                </h3>
                <div className="flex items-center gap-2">
                    <div className="flex gap-1 text-[11px] font-mono uppercase tracking-widest px-3 py-1 bg-muted rounded-full text-foreground border border-border">
                        <span className="text-primary font-bold">●</span> {market.timeframe || 'live'}
                    </div>
                    <div className="flex rounded-full border border-border bg-muted/40 p-0.5">
                        {[
                            { key: '120', label: '120' },
                            { key: '360', label: '360' },
                            { key: '720', label: '720' },
                            { key: '1200', label: '1200' },
                            { key: '2000', label: '2000' },
                            { key: 'all', label: 'ALL' },
                        ].map((item) => (
                            <button
                                key={item.key}
                                onClick={() => setRange(item.key as '120' | '360' | '720' | '1200' | '2000' | 'all')}
                                className={`px-2 py-1 text-[10px] rounded-full transition-colors ${range === item.key ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'
                                    }`}
                            >
                                {item.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="mb-2 text-[10px] text-muted-foreground flex items-center gap-3">
                <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sky-400" /> EMA20</span>
                <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-primary/70" /> Volume</span>
                {(position as any)?.entry_price ? <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /> Entry/SL/TP</span> : null}
            </div>
            <div className="mb-2 grid grid-cols-2 xl:grid-cols-5 gap-1.5 text-[10px]">
                <div className="px-2 py-1 rounded bg-muted/30 border border-border/60">O: {infoCandle?.open?.toFixed?.(2) ?? '--'}</div>
                <div className="px-2 py-1 rounded bg-muted/30 border border-border/60">H: {infoCandle?.high?.toFixed?.(2) ?? '--'}</div>
                <div className="px-2 py-1 rounded bg-muted/30 border border-border/60">L: {infoCandle?.low?.toFixed?.(2) ?? '--'}</div>
                <div className="px-2 py-1 rounded bg-muted/30 border border-border/60">C: {infoCandle?.close?.toFixed?.(2) ?? '--'}</div>
                <div className="px-2 py-1 rounded bg-muted/30 border border-border/60">
                    EMA20: {ema20Data.length ? ema20Data[ema20Data.length - 1].value.toFixed(2) : '--'}
                </div>
            </div>
            <div ref={chartContainerRef} className="flex-1 relative" />
        </div>
    );
};
