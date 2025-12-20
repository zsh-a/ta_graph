import { useStore } from '../store';
import { DollarSign, TrendingDown, Target, ShieldCheck } from 'lucide-react';

const StatCard = ({ label, value, subValue, icon: Icon, colorClass }: any) => (
    <div className="glass-card p-4 flex-1">
        <div className="flex justify-between items-start mb-1">
            <span className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{label}</span>
            <Icon size={16} className={colorClass} />
        </div>
        <div className="flex items-baseline gap-2">
            <h2 className="text-2xl font-bold tracking-tight">{value}</h2>
            {subValue && <span className={`text-xs font-bold ${colorClass}`}>{subValue}</span>}
        </div>
    </div>
);

export const StatsDashboard = () => {
    const { trading, safety } = useStore();
    const pnl = trading.total_pnl || 0;
    const isPositive = pnl >= 0;

    return (
        <div className="grid grid-cols-4 gap-2">
            <StatCard
                label="Net Realized PnL"
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
                value={safety.equity_protector?.is_active ? "ENABLED" : "ACTIVE"}
                subValue={`${safety.error_count || 0} ERRS`}
                icon={ShieldCheck}
                colorClass="text-primary"
            />
        </div>
    );
};
