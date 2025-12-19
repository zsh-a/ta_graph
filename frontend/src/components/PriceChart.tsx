import { useEffect, useRef } from 'react';
import { createChart, ColorType, AreaSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { useStore } from '../store';

export const PriceChart = () => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const lineSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
    const { prices } = useStore();

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#d1d5db',
            },
            grid: {
                vertLines: { color: '#262626' },
                horzLines: { color: '#262626' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
            timeScale: {
                borderColor: '#262626',
                timeVisible: true,
                secondsVisible: false,
            },
            rightPriceScale: {
                borderColor: '#262626',
            },
            crosshair: {
                vertLine: { labelBackgroundColor: '#10b981' },
                horzLine: { labelBackgroundColor: '#10b981' },
            },
        });

        const series = chart.addSeries(AreaSeries, {
            lineColor: '#10b981',
            topColor: 'rgba(16, 185, 129, 0.4)',
            bottomColor: 'rgba(16, 185, 129, 0.0)',
            lineWidth: 2,
        });

        chartRef.current = chart;
        lineSeriesRef.current = series as ISeriesApi<"Area">;

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    useEffect(() => {
        if (lineSeriesRef.current && prices.length > 0) {
            lineSeriesRef.current.setData(prices as any);
        }
    }, [prices]);

    return (
        <div className="flex-1 glass-card p-4 flex flex-col min-h-[400px]">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                    <div className="w-2 h-4 bg-primary rounded-sm" />
                    Market Visualization (BTC/USDT)
                </h3>
                <div className="flex gap-2 text-xs font-mono uppercase tracking-widest px-3 py-1 bg-muted rounded-full text-foreground border border-border">
                    <span className="text-primary font-bold">●</span> Live Stream
                </div>
            </div>
            <div ref={chartContainerRef} className="flex-1 relative" />
        </div>
    );
};
