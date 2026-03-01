import React from 'react';
import { StatsDashboard } from '../components/StatsDashboard';
import { PriceChart } from '../components/PriceChart';
import { AIBrainTerminal } from '../components/AIBrainTerminal';
import { PositionDisplay } from '../components/PositionDisplay';

export const CockpitView: React.FC = () => {
    const [mobilePanel, setMobilePanel] = React.useState<'position' | 'log'>('position');

    return (
        <>
            <StatsDashboard />
            <div className="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-2 md:gap-3">
                <div className="min-h-0 flex flex-col">
                    <PriceChart />
                    <div className="xl:hidden mt-2 grid grid-cols-2 gap-2">
                        <button
                            onClick={() => setMobilePanel('position')}
                            className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-colors ${
                                mobilePanel === 'position'
                                    ? 'bg-primary/15 border-primary/40 text-primary'
                                    : 'bg-muted/20 border-border text-muted-foreground'
                            }`}
                        >
                            Position
                        </button>
                        <button
                            onClick={() => setMobilePanel('log')}
                            className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-colors ${
                                mobilePanel === 'log'
                                    ? 'bg-primary/15 border-primary/40 text-primary'
                                    : 'bg-muted/20 border-border text-muted-foreground'
                            }`}
                        >
                            AI Log
                        </button>
                    </div>
                </div>
                <div className="min-h-0 flex flex-col gap-2 md:gap-3">
                    <div className={mobilePanel === 'position' ? 'block' : 'hidden xl:block'}>
                        <PositionDisplay />
                    </div>
                    <div className={`min-h-0 flex-1 ${mobilePanel === 'log' ? 'block' : 'hidden xl:block'}`}>
                        <AIBrainTerminal className="h-[420px] xl:h-full" />
                    </div>
                </div>
            </div>
        </>
    );
};
