import { useStore } from '../store';
import { DollarSign, TrendingDown, Target, ShieldCheck, BrainCircuit } from 'lucide-react';

const StatCard = ({ label, value, subValue, icon: Icon, colorClass }: any) => (
    <div className="glass-card p-4">
        <div className="flex justify-between items-start mb-1">
            <span className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{label}</span>
            <Icon size={16} className={colorClass} />
        </div>
        <div className="flex items-baseline gap-2">
            <h2 className="text-xl md:text-2xl font-bold tracking-tight">{value}</h2>
            {subValue && <span className={`text-xs font-bold ${colorClass}`}>{subValue}</span>}
        </div>
    </div>
);

const DriftSparkline = ({ values }: { values: number[] }) => {
    if (!values.length) {
        return <div className="h-8 rounded bg-muted/30 border border-border/60" />;
    }

    const width = 120;
    const height = 32;
    const min = 0;
    const max = 10;
    const stepX = values.length > 1 ? width / (values.length - 1) : width;

    const points = values
        .map((v, i) => {
            const x = i * stepX;
            const y = height - ((Math.min(max, Math.max(min, v)) - min) / (max - min)) * height;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');

    const latest = values[values.length - 1];
    const latestX = (values.length - 1) * stepX;
    const latestY = height - ((Math.min(max, Math.max(min, latest)) - min) / (max - min)) * height;
    const y5 = height - ((5 - min) / (max - min)) * height;
    const y8 = height - ((8 - min) / (max - min)) * height;

    return (
        <div className="h-8 w-[120px]">
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-visible">
                <line x1="0" y1={y8} x2={width} y2={y8} stroke="rgba(16,185,129,0.3)" strokeWidth="1" strokeDasharray="2 2" />
                <line x1="0" y1={y5} x2={width} y2={y5} stroke="rgba(239,68,68,0.35)" strokeWidth="1" strokeDasharray="2 2" />
                <line x1="0" y1={height} x2={width} y2={height} stroke="rgba(148,163,184,0.3)" strokeWidth="1" />
                <polyline
                    fill="none"
                    stroke="rgba(56,189,248,0.9)"
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    points={points}
                />
                {values.map((v, i) => {
                    const x = i * stepX;
                    const y = height - ((Math.min(max, Math.max(min, v)) - min) / (max - min)) * height;
                    const isCritical = v < 5;
                    return (
                        <circle
                            key={`${i}-${v}`}
                            cx={x}
                            cy={y}
                            r={isCritical ? 2.2 : 1.6}
                            fill={isCritical ? 'rgba(239,68,68,0.95)' : 'rgba(125,211,252,0.85)'}
                        >
                            <title>{`#${i + 1}: ${v.toFixed(1)}/10`}</title>
                        </circle>
                    );
                })}
                <circle cx={latestX} cy={latestY} r="2.8" fill="rgba(16,185,129,0.95)" />
            </svg>
        </div>
    );
};

export const StatsDashboard = () => {
    const trading = useStore((state) => state.trading);
    const safety = useStore((state) => state.safety);
    const analysis = useStore((state) => state.analysis);
    const driftHistory = useStore((state) => state.driftHistory);
    const pnl = trading.total_pnl || 0;
    const isPositive = pnl >= 0;
    const latest = Number.isFinite(analysis.drift_score) ? analysis.drift_score : 0;
    const last10 = driftHistory.slice(-10);
    const avg10 = last10.length
        ? (last10.reduce((sum, v) => sum + v, 0) / last10.length)
        : 0;
    const spark20 = driftHistory.slice(-20);
    const reliabilityClass = avg10 >= 8 ? 'text-primary' : avg10 >= 6 ? 'text-amber-400' : 'text-destructive';

    return (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 md:gap-3">
            <StatCard
                label="Net PnL"
                value={`$${pnl.toFixed(2)}`}
                subValue={trading.pnl_percentage ? `${trading.pnl_percentage >= 0 ? '+' : ''}${trading.pnl_percentage.toFixed(2)}%` : '--'}
                icon={DollarSign}
                colorClass={isPositive ? 'text-primary' : 'text-destructive'}
            />
            <StatCard
                label="Win Rate"
                value={`${trading.total_trades > 0 ? ((trading.winning_trades / trading.total_trades) * 100).toFixed(1) : 0}%`}
                subValue={`${trading.winning_trades}/${trading.total_trades}`}
                icon={Target}
                colorClass="text-secondary"
            />
            <StatCard
                label="Drawdown"
                value={`${trading.drawdown_percent ? trading.drawdown_percent.toFixed(2) : '0.00'}%`}
                subValue={`Peak: $${trading.max_drawdown ? trading.max_drawdown.toFixed(2) : '0.00'}`}
                icon={TrendingDown}
                colorClass="text-accent"
            />
            <StatCard
                label="Risk Guard"
                value={safety.equity_protector?.is_active ? 'ENABLED' : 'ACTIVE'}
                subValue={`${safety.error_count || 0} ERRS`}
                icon={ShieldCheck}
                colorClass="text-primary"
            />
            <StatCard
                label="Model Reliability"
                value={`${avg10.toFixed(1)}/10`}
                subValue={`L:${latest.toFixed(1)} N:${driftHistory.length}`}
                icon={BrainCircuit}
                colorClass={reliabilityClass}
            />
            <div className="glass-card p-4 col-span-2 lg:col-span-1">
                <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">Reliability Trend</span>
                    <span className={`text-xs font-bold ${reliabilityClass}`}>{avg10.toFixed(1)}</span>
                </div>
                <div className="flex items-end justify-between gap-2">
                    <DriftSparkline values={spark20} />
                    <div className="text-[10px] text-muted-foreground text-right">
                        <div>20 pts</div>
                        <div>red &lt; 5.0</div>
                    </div>
                </div>
            </div>
        </div>
    );
};
