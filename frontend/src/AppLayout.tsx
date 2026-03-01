import React from 'react';
import { Zap } from 'lucide-react';
import { useStore } from './store';

export const AppLayout = ({ children }: { children: React.ReactNode }) => {
    const status = useStore((state) => state.status);

    return (
        <div className="h-screen bg-background text-foreground overflow-hidden p-2 md:p-3">
            <div className="h-full flex flex-col gap-2 md:gap-3">
                <header className="glass-card px-4 py-3 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary rounded-lg">
                            <Zap className="text-primary-foreground" size={18} />
                        </div>
                        <div>
                            <h1 className="font-bold text-lg tracking-tight">ta_graph</h1>
                            <p className="text-[11px] text-muted-foreground uppercase tracking-wider">Execution Cockpit</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-semibold">
                        <span className={`w-2.5 h-2.5 rounded-full ${status === 'online' ? 'bg-primary' : 'bg-destructive'} animate-pulse`} />
                        <span className="uppercase tracking-wider text-muted-foreground">{status}</span>
                    </div>
                </header>

                <main className="flex-1 flex flex-col gap-2 md:gap-3 min-h-0">
                    {children}
                </main>
            </div>
        </div>
    );
};
