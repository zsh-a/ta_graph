import { AppLayout } from './AppLayout';
import { useWebSocket } from './hooks/useWebSocket';
import { useStore } from './store';
import { getWsUrl } from './lib/api';
import { CockpitView } from './views/CockpitView';

import { formatTradingPair } from './lib/market';

function App() {
  const wsUrl = getWsUrl();
  useWebSocket(wsUrl);
  const market = useStore((state) => state.market);
  const position = useStore((state) => state.trading.current_position);
  const analysis = useStore((state) => state.analysis);

  const activePair = formatTradingPair(position?.symbol || market.symbol);
  const exchange = (market.exchange || 'N/A').toUpperCase();
  const timeframe = market.timeframe || '--';
  const lastPrice = Number.isFinite(market.current_price) ? market.current_price : 0;
  const change24h = Number.isFinite(market.price_change_24h) ? market.price_change_24h : 0;
  const driftScore = Number.isFinite(analysis.drift_score) ? analysis.drift_score : 0;
  const consistencyClass = driftScore >= 8 ? 'text-primary' : driftScore >= 6 ? 'text-amber-400' : 'text-destructive';
  const changedFields = analysis.changed_fields?.length ? analysis.changed_fields.join(', ') : 'none';
  const consistencyHint = `Changed: ${changedFields} | Δbuy:${analysis.buying_pressure_delta ?? 0} Δsell:${analysis.selling_pressure_delta ?? 0} | warnings:${analysis.warning_count} errors:${analysis.error_count}`;

  return (
    <AppLayout>
      <div className="px-4 py-3 glass-card border-primary/20">
        <div className="flex flex-wrap items-center gap-4 xl:gap-6">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Active Pair</span>
            <span className="text-xl font-bold tracking-tight">
              {activePair} <span className="text-muted-foreground font-normal">/ {exchange}</span>
            </span>
          </div>
          <div className="hidden md:block h-8 w-[1px] bg-border" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Timeframe</span>
            <span className="font-semibold">{timeframe}</span>
          </div>
          <div className="hidden md:block h-8 w-[1px] bg-border" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Last Price</span>
            <span className="font-semibold">${lastPrice > 0 ? lastPrice.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '--'}</span>
          </div>
          <div className="hidden md:block h-8 w-[1px] bg-border" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">24h Change</span>
            <span className={`font-semibold ${change24h >= 0 ? 'text-primary' : 'text-destructive'}`}>
              {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
            </span>
          </div>
          <div className="hidden md:block h-8 w-[1px] bg-border" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Context Consistency</span>
            <span className={`font-semibold ${consistencyClass}`} title={consistencyHint}>
              {driftScore.toFixed(1)}/10
            </span>
            <span className="text-[10px] text-muted-foreground">
              W{analysis.warning_count} E{analysis.error_count}
            </span>
          </div>
        </div>
      </div>

      <CockpitView />
    </AppLayout>
  );
}

export default App;
