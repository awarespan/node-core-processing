import React from 'react';
import { ConnectionState } from '../types';

interface StatusBadgeProps {
  state: ConnectionState;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, className = '' }) => {
  const getStatusConfig = (s: ConnectionState) => {
    switch (s) {
      case 'BOTH_CONNECTED':
        return {
          label: 'BOTH SOURCES ACTIVE',
          bg: 'bg-emerald-950/60',
          text: 'text-emerald-400',
          border: 'border-emerald-600',
          dot: 'bg-emerald-400 animate-pulse',
        };
      case 'CAMERA_CONNECTED':
        return {
          label: 'CAMERA ACTIVE (PI ACK)',
          bg: 'bg-emerald-950/60',
          text: 'text-emerald-400',
          border: 'border-emerald-600',
          dot: 'bg-emerald-400 animate-pulse',
        };
      case 'MICROPHONE_CONNECTED':
        return {
          label: 'MIC ACTIVE (PI ACK)',
          bg: 'bg-emerald-950/60',
          text: 'text-emerald-400',
          border: 'border-emerald-600',
          dot: 'bg-emerald-400 animate-pulse',
        };
      case 'CONNECTING':
        return {
          label: 'CONNECTING TO PI...',
          bg: 'bg-amber-950/60',
          text: 'text-amber-400',
          border: 'border-amber-600',
          dot: 'bg-amber-400 animate-ping',
        };
      case 'AWAITING_PI_ACK':
        return {
          label: 'AWAITING PI ACK',
          bg: 'bg-amber-950/60',
          text: 'text-amber-400',
          border: 'border-amber-600',
          dot: 'bg-amber-400 animate-bounce',
        };
      case 'RECONNECTING':
        return {
          label: 'RECONNECTING...',
          bg: 'bg-amber-950/60',
          text: 'text-amber-400',
          border: 'border-amber-600',
          dot: 'bg-amber-400 animate-ping',
        };
      case 'AUTHENTICATING':
        return {
          label: 'AUTHENTICATING',
          bg: 'bg-blue-950/60',
          text: 'text-blue-400',
          border: 'border-blue-600',
          dot: 'bg-blue-400',
        };
      case 'PERMISSION_DENIED':
        return {
          label: 'PERMISSION DENIED',
          bg: 'bg-red-950/60',
          text: 'text-red-400',
          border: 'border-red-600',
          dot: 'bg-red-400',
        };
      case 'CONNECTION_LOST':
        return {
          label: 'CONNECTION LOST',
          bg: 'bg-red-950/60',
          text: 'text-red-400',
          border: 'border-red-600',
          dot: 'bg-red-400',
        };
      case 'BACKEND_UNAVAILABLE':
        return {
          label: 'PI UNAVAILABLE',
          bg: 'bg-red-950/60',
          text: 'text-red-400',
          border: 'border-red-600',
          dot: 'bg-red-400',
        };
      case 'SESSION_EXPIRED':
        return {
          label: 'SESSION EXPIRED',
          bg: 'bg-[#1a1a1a]',
          text: 'text-[#ff4f2b]',
          border: 'border-[#ff4f2b]',
          dot: 'bg-[#ff4f2b]',
        };
      case 'STOPPED_BY_USER':
        return {
          label: 'STOPPED',
          bg: 'bg-[#1a1a1a]',
          text: 'text-[#bfbfbf]',
          border: 'border-[#3c3c3c]',
          dot: 'bg-[#737373]',
        };
      case 'NOT_CONNECTED':
      default:
        return {
          label: 'IDLE / DISCONNECTED',
          bg: 'bg-[#1a1a1a]',
          text: 'text-[#737373]',
          border: 'border-[#3c3c3c]',
          dot: 'bg-[#737373]',
        };
    }
  };

  const conf = getStatusConfig(state);

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 text-xs font-mono tracking-wider border ${conf.bg} ${conf.text} ${conf.border} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-none ${conf.dot}`} />
      <span>{conf.label}</span>
    </div>
  );
};
