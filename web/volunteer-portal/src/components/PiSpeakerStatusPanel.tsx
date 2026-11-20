import React from 'react';
import { AudioLines, ShieldCheck, ShieldAlert, HelpCircle } from 'lucide-react';
import { useVolunteer } from '../context/VolunteerContext';

export const PiSpeakerStatusPanel: React.FC = () => {
  const { piCapabilities } = useVolunteer();
  const detected = piCapabilities?.speaker_output_available === true;
  const known = piCapabilities !== null;

  return (
    <section className="border border-[#3c3c3c] bg-[#1a1a1a] mb-6">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#3c3c3c] bg-[#000000]">
        <div className="flex items-center gap-2">
          <AudioLines className="w-4 h-4 text-[#ff4f2b]" />
          <h2 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]">NODE AUDIO HARDWARE OWNERSHIP</h2>
        </div>
        <span className="text-[10px] font-mono text-[#737373]">NODE-CONTROLLED</span>
      </div>
      <div className="p-4 flex items-start gap-3">
        {detected ? <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" /> : known ? <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" /> : <HelpCircle className="w-5 h-5 text-[#737373] shrink-0" />}
        <div className="min-w-0">
          <div className="text-sm text-[#f5f5f5]">
            {detected ? 'Node audio output interface detected — audio belongs to the node.' : known ? 'No node playback interface reported.' : 'Waiting for the node to report audio capabilities.'}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[#bfbfbf]">
            {detected
              ? 'The portal will not request microphone access or offer an audio source. The active node alone controls its local output.'
              : 'Browser microphone donation remains disabled until the node confirms that an audio input path is configured. The portal never plays deterrence audio locally.'}
          </p>
          {piCapabilities?.speaker_output_cards?.length ? (
            <div className="mt-2 text-[10px] font-mono text-[#737373] break-words">{piCapabilities.speaker_output_cards.join(' · ')}</div>
          ) : null}
          {piCapabilities?.speaker_output_reason && !detected ? (
            <div className="mt-1 text-[10px] font-mono text-[#737373]">Probe: {piCapabilities.speaker_output_reason}</div>
          ) : null}
        </div>
      </div>
    </section>
  );
};
