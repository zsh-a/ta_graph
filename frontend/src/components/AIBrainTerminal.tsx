import ReactMarkdown from 'react-markdown';
import { useStore } from '../store';
import { Terminal, Cpu, Info, AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react';

const LogIcon = ({ type }: { type: string }) => {
    switch (type) {
        case 'thinking': return <Cpu className="text-secondary animate-pulse" size={14} />;
        case 'info': return <Info className="text-muted-foreground" size={14} />;
        case 'error': return <AlertTriangle className="text-destructive" size={14} />;
        case 'success': return <CheckCircle className="text-primary" size={14} />;
        case 'decision': return <TrendingUp className="text-accent" size={14} />;
        default: return <Terminal size={14} />;
    }
};

export const AIBrainTerminal = () => {
    const { logs } = useStore();

    return (
        <div className="w-96 glass-card p-4 flex flex-col h-full">
            <div className="flex justify-between items-center mb-4 border-b border-border pb-2">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                    <Terminal size={16} />
                    AI Execution Log
                </h3>
                <span className="text-[10px] font-mono bg-muted px-2 py-0.5 rounded text-muted-foreground">
                    {logs.length} EVENTS
                </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
                {logs.map((log) => (
                    <div key={log.id} className="group border-b border-border/30 pb-3 last:border-0">
                        <div className="flex items-center gap-2 mb-1">
                            <LogIcon type={log.type} />
                            <span className="text-[10px] font-mono text-muted-foreground uppercase opacity-70">
                                {new Date(log.timestamp).toLocaleTimeString()} · {log.node}
                            </span>
                        </div>
                        <div className="terminal-text text-foreground/90 pl-5">
                            {log.type === 'thinking' ? (
                                <div className="flex items-center gap-2">
                                    <span className="w-1 h-3 bg-secondary rounded-full animate-pulse" />
                                    {log.message}
                                </div>
                            ) : (
                                <div className="markdown-content">
                                    <ReactMarkdown>{log.message}</ReactMarkdown>
                                </div>
                            )}
                        </div>

                        {log.data && log.type === 'decision' && (
                            <div className="mt-2 ml-5 p-2 bg-accent/5 border border-accent/20 rounded-md text-[10px] font-mono">
                                <div className="flex justify-between">
                                    <span className="text-accent uppercase">Action: {log.data.operation}</span>
                                    <span className="text-muted-foreground">Prob: {log.data.probability_score}%</span>
                                </div>
                            </div>
                        )}

                        {log.data && log.type === 'success' && log.data.signal_bar && (
                            <div className="mt-2 ml-5 p-2 bg-primary/5 border border-primary/20 rounded-md text-[10px] font-mono">
                                <div className="flex justify-between">
                                    <span className="text-primary uppercase">Bar Quality: {log.data.signal_bar.quality_score}/10</span>
                                    <span className="text-muted-foreground">{log.data.signal_bar.bar_type}</span>
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {logs.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center opacity-30 text-center">
                        <Terminal size={48} className="mb-2" />
                        <p className="text-xs uppercase tracking-widest font-bold">Waiting for system tick...</p>
                    </div>
                )}
            </div>
        </div>
    );
};
