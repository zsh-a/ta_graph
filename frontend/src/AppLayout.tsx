import React from 'react';
import { Activity, LayoutDashboard, Brain, PieChart, ShieldAlert, Zap } from 'lucide-react';
import { useStore } from './store';

interface SidebarItemProps {
    icon: React.ElementType;
    label: string;
    active?: boolean;
    onClick?: () => void;
}

const SidebarItem = ({ icon: Icon, label, active, onClick }: SidebarItemProps) => (
    <div
        onClick={onClick}
        className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all duration-200 ${active ? 'bg-primary/20 text-primary border-l-4 border-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}>
        <Icon size={20} />
        <span className="font-medium text-sm">{label}</span>
    </div>
);

export const AppLayout = ({ children }: { children: React.ReactNode }) => {
    const { status, currentView, setView } = useStore();

    return (
        <div className="flex h-screen bg-background text-foreground overflow-hidden">
            {/* Sidebar */}
            <aside className="w-64 border-r border-border flex flex-col glass-card m-2 rounded-xl">
                <div className="p-6 flex items-center gap-3 border-b border-border">
                    <div className="p-2 bg-primary rounded-lg">
                        <Zap className="text-primary-foreground" size={24} />
                    </div>
                    <div>
                        <h1 className="font-bold text-lg tracking-tight">ta_graph</h1>
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-primary' : 'bg-destructive'} animate-pulse`} />
                            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">{status}</span>
                        </div>
                    </div>
                </div>

                <nav className="flex-1 p-3 space-y-1">
                    <SidebarItem
                        icon={LayoutDashboard}
                        label="Cockpit"
                        active={currentView === 'cockpit'}
                        onClick={() => setView('cockpit')}
                    />
                    <SidebarItem
                        icon={Activity}
                        label="Live Charts"
                        active={currentView === 'charts'}
                        onClick={() => setView('charts')}
                    />
                    <SidebarItem
                        icon={Brain}
                        label="AI Reasoning"
                        active={currentView === 'reasoning'}
                        onClick={() => setView('reasoning')}
                    />
                    <SidebarItem
                        icon={PieChart}
                        label="Portfolio"
                        active={currentView === 'portfolio'}
                        onClick={() => setView('portfolio')}
                    />
                    <SidebarItem
                        icon={ShieldAlert}
                        label="Safety & Logs"
                        active={currentView === 'safety'}
                        onClick={() => setView('safety')}
                    />
                </nav>

                <div className="p-4 border-t border-border">
                    <div className="p-4 bg-muted/50 rounded-lg">
                        <div className="flex justify-between items-center mb-2">
                            <span className="text-xs text-muted-foreground font-medium">Session Health</span>
                            <span className="text-xs text-primary font-bold">100%</span>
                        </div>
                        <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                            <div className="bg-primary h-full w-full" />
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col p-2 gap-2 overflow-hidden">
                {children}
            </main>
        </div>
    );
};
