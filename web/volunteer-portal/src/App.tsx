import React, { useState } from 'react';
import { Header } from './components/Header';
import { OverviewSection } from './components/OverviewSection';
import { TestMediaSubmission } from './components/TestMediaSubmission';
import { VolunteerControls } from './components/VolunteerControls';
import { MediaPreview } from './components/MediaPreview';
import { PiSpeakerStatusPanel } from './components/PiSpeakerStatusPanel';
import { DetectionEvidence } from './components/DetectionEvidence';
import { SessionMonitor } from './components/SessionMonitor';
import { TerminalLogs } from './components/TerminalLogs';
import { LoginModal } from './components/LoginModal';
import { ConfigModal } from './components/ConfigModal';
import { BackendContractDocs } from './components/BackendContractDocs';
import { ShieldAlert, Info } from 'lucide-react';

export const App: React.FC = () => {
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isDocsOpen, setIsDocsOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#000000] text-[#f5f5f5] flex flex-col font-mono selection:bg-[#ff4f2b] selection:text-black">
      {/* Top sticky navigation bar */}
      <Header
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenConfig={() => setIsConfigOpen(true)}
        onOpenDocs={() => setIsDocsOpen(true)}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-[1280px] w-full mx-auto px-4 sm:px-6 py-8">
        {/* Hero Section Banner */}
        <section className="mb-8 border border-[#3c3c3c] bg-[#000000] p-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-48 h-full bg-gradient-to-l from-[#ff4f2b]/10 to-transparent pointer-events-none" />
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="text-xs font-mono uppercase text-[#ff4f2b] tracking-widest mb-1.5 flex items-center gap-2">
                <span className="w-2 h-2 bg-[#ff4f2b] inline-block" />
                <span>AWARESPAN ECOSYSTEM // TEMPORARY INPUT NODE</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-light text-[#f5f5f5] tracking-tight">
                Volunteer Camera Portal
              </h1>
              <p className="text-xs text-[#bfbfbf] max-w-2xl mt-2 leading-relaxed">
                Allows authorized operator devices to volunteer camera input as an auxiliary observation feed
                for the active AWARESPAN Linux edge node. Audio output remains node-owned; browser microphone
                donation is disabled until a live node-side input pipeline is available.
              </p>
            </div>

            <div className="shrink-0 flex items-center gap-2 text-xs text-[#737373]">
              <Info className="w-4 h-4 text-[#ff4f2b]" />
              <span>Edge AI models execute on the active node</span>
            </div>
          </div>
        </section>

        {/* 1. Overview Section */}
        <OverviewSection />

        {/* 1.1 Test Media Submission Interface */}
        <TestMediaSubmission />

        {/* 2. Node-owned output capability and volunteer source guards */}
        <PiSpeakerStatusPanel />

        {/* 3. Volunteer Device Controls */}
        <VolunteerControls onOpenAuthPrompt={() => setIsAuthOpen(true)} />

        {/* 4. Media Preview (Camera & Mic Activity) */}
        <MediaPreview />

        {/* 5. Annotated evidence returned by the node */}
        <DetectionEvidence />

        {/* 6. Live Session Telemetry */}
        <SessionMonitor />

        {/* 7. Terminal Event Console */}
        <TerminalLogs />

        {/* Architectural Notice Card */}
        <section className="border border-[#3c3c3c] bg-[#1a1a1a] p-4 text-xs text-[#bfbfbf] flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-[#ff4f2b] shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="text-[#f5f5f5] font-semibold uppercase">
              Security &amp; Architectural Isolation Notice
            </div>
            <p>
              This portal does not perform AI threat detection, does not store media recordings in cloud storage,
              and contains no Telegram bot tokens. All operational threat decisions and Telegram notifications
              originate authoritatively from the active edge node.
            </p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-[#3c3c3c] bg-[#000000] py-6 text-xs text-[#737373]">
        <div className="max-w-[1280px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 font-mono">
            <span className="text-[#ff4f2b]">AWARESPAN</span>
            <span>—</span>
            <span>Awareness Without Boundaries.</span>
          </div>

          <div className="flex items-center gap-4 font-mono text-[11px]">
            <button
              onClick={() => setIsDocsOpen(true)}
              className="hover:text-[#f5f5f5] transition-colors cursor-pointer"
            >
              Backend Contract
            </button>
            <span>//</span>
            <button
              onClick={() => setIsConfigOpen(true)}
              className="hover:text-[#f5f5f5] transition-colors cursor-pointer"
            >
              Target Node Settings
            </button>
            <span>//</span>
            <span>v1.0.0-temp</span>
          </div>
        </div>
      </footer>

      {/* Modals */}
      <LoginModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
      <ConfigModal isOpen={isConfigOpen} onClose={() => setIsConfigOpen(false)} />
      <BackendContractDocs isOpen={isDocsOpen} onClose={() => setIsDocsOpen(false)} />
    </div>
  );
};
