import React, { useState } from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { Terminal, Trash2, Filter } from 'lucide-react';
import { LogCategory } from '../types';

export const TerminalLogs: React.FC = () => {
  const { logs, clearLogs } = useVolunteer();
  const [filter, setFilter] = useState<LogCategory | 'all'>('all');

  const filteredLogs = filter === 'all' ? logs : logs.filter((l) => l.category === filter);

  const getLevelBadge = (level: string) => {
    switch (level) {
      case 'success':
        return <span className="text-emerald-400 font-bold">[OK]</span>;
      case 'warn':
        return <span className="text-amber-400 font-bold">[WARN]</span>;
      case 'error':
        return <span className="text-red-400 font-bold">[ERR]</span>;
      case 'info':
      default:
        return <span className="text-[#bfbfbf]">[INFO]</span>;
    }
  };

  return (
    <div className="border border-[#3c3c3c] bg-[#1a1a1a] mb-8">
      {/* Console Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#3c3c3c] bg-[#000000]">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#ff4f2b]" />
          <span className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]">
            SYSTEM AUDIT &amp; CONNECTION LOG
          </span>
          <span className="text-[10px] font-mono text-[#737373]">
            ({filteredLogs.length} events)
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Category Filter */}
          <div className="flex items-center gap-1 text-[11px] font-mono text-[#737373]">
            <Filter className="w-3 h-3 text-[#ff4f2b]" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as LogCategory | 'all')}
              className="bg-[#1a1a1a] border border-[#3c3c3c] text-xs font-mono text-[#bfbfbf] px-2 py-0.5 outline-none cursor-pointer"
            >
              <option value="all">ALL CATEGORIES</option>
              <option value="auth">AUTH</option>
              <option value="network">NETWORK</option>
              <option value="media">MEDIA</option>
              <option value="ack">ACK</option>
              <option value="system">SYSTEM</option>
            </select>
          </div>

          <button
            onClick={clearLogs}
            className="text-[#737373] hover:text-[#f5f5f5] p-1 cursor-pointer transition-colors"
            title="Clear Event Log"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div className="h-56 overflow-y-auto p-4 bg-[#000000] font-mono text-xs space-y-1.5 select-text">
        {filteredLogs.length === 0 ? (
          <div className="text-[#737373] italic">
            &gt; Waiting for operational events...
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="flex items-start gap-2 leading-relaxed">
              <span className="text-[#737373] shrink-0">{log.timestamp}</span>
              {getLevelBadge(log.level)}
              <span className="text-[#737373] uppercase shrink-0">
                [{log.category}]
              </span>
              <span
                className={`break-all ${
                  log.level === 'error'
                    ? 'text-red-400'
                    : log.level === 'warn'
                    ? 'text-amber-300'
                    : log.level === 'success'
                    ? 'text-emerald-300'
                    : 'text-[#f5f5f5]'
                }`}
              >
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
