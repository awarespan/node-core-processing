import React, { useState, useEffect } from 'react';
import { useVolunteer } from '../context/VolunteerContext';
import { StatusBadge } from './StatusBadge';
import { Shield, Settings, LogOut, Lock, Radio } from 'lucide-react';

interface HeaderProps {
  onOpenAuth: () => void;
  onOpenConfig: () => void;
  onOpenDocs: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenAuth, onOpenConfig, onOpenDocs }) => {
  const { connectionState, session, logout, config } = useVolunteer();
  const [timeLeft, setTimeLeft] = useState<string>('');

  useEffect(() => {
    if (!session) {
      setTimeLeft('');
      return;
    }

    const updateTimer = () => {
      const remainingMs = session.expiresAt - Date.now();
      if (remainingMs <= 0) {
        setTimeLeft('EXPIRED');
      } else {
        const mins = Math.floor(remainingMs / 60000);
        const secs = Math.floor((remainingMs % 60000) / 1000);
        setTimeLeft(`${mins}:${secs < 10 ? '0' : ''}${secs}`);
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [session]);

  return (
    <header className="w-full bg-[#000000] border-b border-[#3c3c3c] sticky top-0 z-40">
      {/* Top micro banner for Dev/Mock notice */}
      {config.mockMode && (
        <div className="bg-[#1a1a1a] border-b border-[#3c3c3c] text-center py-1 px-4 text-xs font-mono text-[#bfbfbf] flex items-center justify-center gap-2">
          <span className="w-2 h-2 bg-[#ff4f2b] inline-block" />
          <span>DEV / MOCK MODE ACTIVE — Hardware simulation enabled.</span>
          <button
            onClick={onOpenConfig}
            className="text-[#ff4f2b] underline hover:text-[#f5f5f5] ml-2 cursor-pointer"
          >
            Switch to Live Pi Target
          </button>
        </div>
      )}

      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand Wordmark */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-[#ff4f2b] flex items-center justify-center text-black font-mono font-bold text-sm tracking-tighter">
            AS
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-mono text-base font-semibold tracking-wider text-[#f5f5f5]">
                AWARESPAN
              </span>
              <span className="text-[10px] font-mono uppercase bg-[#1a1a1a] text-[#bfbfbf] px-1.5 py-0.5 border border-[#3c3c3c]">
                VOLUNTEER NODE
              </span>
            </div>
            <span className="text-[11px] font-mono text-[#737373] tracking-tight">
              TEMPORARY MEDIA INGESTION PORTAL
            </span>
          </div>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-3 sm:gap-4">
          <StatusBadge state={connectionState} className="hidden md:inline-flex" />

          {/* Node Docs Trigger */}
          <button
            onClick={onOpenDocs}
            className="text-xs font-mono text-[#bfbfbf] hover:text-[#f5f5f5] px-2.5 py-1.5 border border-[#3c3c3c] hover:border-[#bfbfbf] transition-colors flex items-center gap-1.5 cursor-pointer"
            title="Inspect Pi backend contract"
          >
            <Radio className="w-3.5 h-3.5 text-[#ff4f2b]" />
            <span className="hidden sm:inline">CONTRACT</span>
          </button>

          {/* Configuration Trigger */}
          <button
            onClick={onOpenConfig}
            className="text-xs font-mono text-[#bfbfbf] hover:text-[#f5f5f5] p-1.5 border border-[#3c3c3c] hover:border-[#bfbfbf] transition-colors cursor-pointer"
            title="Configure Pi Target Host & Port"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* Authentication State */}
          {session ? (
            <div className="flex items-center gap-2 bg-[#1a1a1a] border border-[#3c3c3c] px-3 py-1">
              <div className="flex flex-col text-right">
                <div className="flex items-center gap-1 text-xs font-mono text-[#f5f5f5]">
                  <Shield className="w-3 h-3 text-[#ff4f2b]" />
                  <span>OP: {session.operatorId}</span>
                </div>
                <span className="text-[10px] font-mono text-[#737373]">
                  EXP: {timeLeft}
                </span>
              </div>
              <button
                onClick={logout}
                className="ml-2 p-1 text-[#bfbfbf] hover:text-[#ff4f2b] transition-colors cursor-pointer"
                title="Logout Operator"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="text-xs font-mono uppercase tracking-wider text-[#000000] bg-[#ff4f2b] hover:bg-[#e04523] px-3.5 py-1.5 font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>AUTHENTICATE</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
