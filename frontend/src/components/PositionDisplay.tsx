import React from 'react';
import { useStore } from '../store';
import { Target, Shield, Zap, ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';

export const PositionDisplay: React.FC = () => {
    const { trading } = useStore();
    const position = trading.current_position;

    if (!position) {
        return (
            <div className="glass-card p-6 flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
                <Activity size={32} className="mb-2 opacity-20" />
                <p className="text-sm font-medium">No Active Positions</p>
                <p className="text-xs opacity-60">System is currently hunting for signals</p>
            </div>
        );
    }

    const isLong = position.side?.toLowerCase() === 'long';
    const pnl = position.unrealized_pnl || 0;
    const pnlColor = pnl >= 0 ? 'text-primary' : 'text-destructive';

    return (
        <div className="glass-card overflow-hidden">
            <div className="p-4 border-b border-white/5 bg-white/5 flex justify-between items-center">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${isLong ? 'bg-primary/20 text-primary' : 'bg-destructive/20 text-destructive'}`}>
                        {isLong ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
                    </div>
                    <div>
                        <h3 className="font-bold tracking-tight">{position.symbol}</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[10px] uppercase font-heavy px-1.5 py-0.5 rounded ${isLong ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'}`}>
                                {position.side?.toUpperCase()}
                            </span>
                            <span className="text-[10px] text-muted-foreground font-bold">
                                {position.leverage}X · {position.margin_type?.toUpperCase()}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="text-right">
                    <div className={`text-xl font-black ${pnlColor}`}>
                        {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">
                        Unrealized PnL
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-px bg-white/5">
                <div className="bg-background/20 p-3">
                    <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1 tracking-tight">Size</div>
                    <div className="text-sm font-mono font-bold">{position.size}</div>
                </div>
                <div className="bg-background/20 p-3">
                    <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1 tracking-tight">Entry</div>
                    <div className="text-sm font-mono font-bold">${position.entry_price?.toFixed(2)}</div>
                </div>
                <div className="bg-background/20 p-3">
                    <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1 tracking-tight">Mark</div>
                    <div className="text-sm font-mono font-bold">${position.mark_price?.toFixed(2)}</div>
                </div>
            </div>

            <div className="p-3 bg-white/5 grid grid-cols-2 gap-3 border-t border-white/5">
                <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/5 border border-primary/10">
                    <Target size={14} className="text-primary" />
                    <div>
                        <div className="text-[9px] uppercase text-muted-foreground font-bold leading-none mb-0.5">Take Profit</div>
                        <div className="text-xs font-mono font-heavy text-primary">
                            {position.take_profit ? `$${position.take_profit.toFixed(2)}` : '--'}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2 p-2 rounded-lg bg-destructive/5 border border-destructive/10">
                    <Shield size={14} className="text-destructive" />
                    <div>
                        <div className="text-[9px] uppercase text-muted-foreground font-bold leading-none mb-0.5">Stop Loss</div>
                        <div className="text-xs font-mono font-heavy text-destructive">
                            {position.stop_loss ? `$${position.stop_loss.toFixed(2)}` : '--'}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
