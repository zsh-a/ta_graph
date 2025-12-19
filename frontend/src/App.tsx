import React from 'react';
import { AppLayout } from './AppLayout';
import { useWebSocket } from './hooks/useWebSocket';
import { useStore } from './store';
import { AlertTriangle, Radiation } from 'lucide-react';

// View Components
import { CockpitView } from './views/CockpitView';
import { ChartsView } from './views/ChartsView';
import { ReasoningView } from './views/ReasoningView';
import { PortfolioView } from './views/PortfolioView';
import { SafetyView } from './views/SafetyView';

/**
 * View mapping for the dashboard navigation.
 * Easily extensible by adding new keys and components here.
 */
const VIEW_MAP: Record<string, React.FC> = {
  cockpit: CockpitView,
  charts: ChartsView,
  reasoning: ReasoningView,
  portfolio: PortfolioView,
  safety: SafetyView,
};

function App() {
  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws';
  const { sendCommand } = useWebSocket(wsUrl);
  const currentView = useStore((state) => state.currentView);

  const handlePanic = () => {
    if (confirm('EMERGENCY: CLEAR ALL POSITIONS AND STOP EXECUTION?')) {
      sendCommand('panic_button', { reason: 'manual_intervention' });
    }
  };

  // Get the active component based on store state
  const ActiveView = VIEW_MAP[currentView] || CockpitView;

  return (
    <AppLayout>
      {/* Top Controls (Static across all views) */}
      <div className="flex justify-between items-center px-4 py-2 glass-card">
        <div className="flex items-center gap-6">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Active Pair</span>
            <span className="text-xl font-bold tracking-tighter">
              BTCUSD.PERP <span className="text-muted-foreground font-normal">/ Bitget</span>
            </span>
          </div>
          <div className="h-8 w-[1px] bg-border" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Strategy</span>
            <span className="text-primary font-bold">Brooks PA Supervisor</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="flex items-center gap-2 px-4 py-2 bg-muted hover:bg-muted-foreground/20 rounded-lg transition-colors text-sm font-bold border border-border"
            onClick={() => sendCommand('manual_approval', { decision: 'approve' })}
          >
            <AlertTriangle size={16} className="text-accent" />
            PENDING APPROVAL
          </button>

          <button
            className="flex items-center gap-2 px-4 py-2 bg-destructive text-destructive-foreground hover:opacity-90 rounded-lg transition-all shadow-lg shadow-destructive/20 font-bold active:scale-95"
            onClick={handlePanic}
          >
            <Radiation size={18} />
            PANIC BUTTON
          </button>
        </div>
      </div>

      {/* Dynamic View Content */}
      <ActiveView />
    </AppLayout>
  );
}

export default App;
