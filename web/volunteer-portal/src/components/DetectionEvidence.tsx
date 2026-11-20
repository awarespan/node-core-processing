import React from 'react';
import { AlertTriangle, Camera, Download, ImageOff } from 'lucide-react';
import { useVolunteer } from '../context/VolunteerContext';

export const DetectionEvidence: React.FC = () => {
  const { detectionEvidence } = useVolunteer();

  return (
    <section className="border border-[#3c3c3c] bg-[#1a1a1a] mb-6">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#3c3c3c] bg-[#000000]">
        <div className="flex items-center gap-2">
          <Camera className="w-4 h-4 text-[#ff4f2b]" />
          <h2 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]">DETECTION EVIDENCE</h2>
        </div>
        <span className="text-[10px] font-mono text-[#737373]">{detectionEvidence.length} RECENT EVENTS</span>
      </div>

      {detectionEvidence.length === 0 ? (
        <div className="p-8 text-center">
          <ImageOff className="w-8 h-8 mx-auto mb-3 text-[#3c3c3c]" />
          <p className="text-xs font-mono text-[#bfbfbf]">No detections received yet.</p>
          <p className="text-[11px] text-[#737373] mt-1">When the Pi reports a threat, its annotated frame will appear here.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
          {detectionEvidence.map(({ event, imageUrl }) => {
            const fileName = `awarespan-${event.event_id}.jpg`;
            return (
              <article key={event.event_id} className="border border-[#3c3c3c] bg-[#000000] min-w-0">
                {imageUrl ? (
                  <a href={imageUrl} target="_blank" rel="noreferrer" aria-label={`Open annotated evidence for ${event.event_id}`}>
                    <img src={imageUrl} alt={`Pi-annotated detection: ${event.labels.join(', ')}`} className="w-full aspect-video object-contain bg-black" />
                  </a>
                ) : (
                  <div className="aspect-video flex flex-col items-center justify-center gap-2 text-[#737373]">
                    <AlertTriangle className="w-6 h-6 text-amber-500" />
                    <span className="text-[11px] font-mono">ANNOTATED FRAME NOT RECEIVED</span>
                  </div>
                )}
                <div className="p-3 border-t border-[#3c3c3c] space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm text-[#f5f5f5]">{event.labels.join(', ') || 'Threat detected'}</div>
                      <div className="text-[10px] font-mono text-[#737373] mt-1">{new Date(event.ts_ms).toLocaleString()}</div>
                    </div>
                    <span className="text-[10px] font-mono text-[#ff4f2b] border border-[#3c3c3c] px-2 py-1 shrink-0">{(event.max_confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] font-mono text-[#737373]">
                    <span>{event.tier.toUpperCase()}</span>
                    <span>FRAME {event.frame_id}</span>
                    <span>{event.source_id || 'UNKNOWN SOURCE'}</span>
                  </div>
                  {imageUrl ? (
                    <a href={imageUrl} download={fileName} className="inline-flex items-center gap-2 px-3 py-2 border border-[#3c3c3c] text-xs font-mono text-[#bfbfbf] hover:border-[#ff4f2b] hover:text-[#f5f5f5]">
                      <Download className="w-3.5 h-3.5 text-[#ff4f2b]" /> Download annotated photo
                    </a>
                  ) : (
                    <span className="text-[10px] text-[#737373]">The event arrived without its matching annotated image.</span>
                  )}
                  <div className="text-[10px] text-[#737373] break-all">EVENT: {event.event_id}</div>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <div className="px-4 py-2 border-t border-[#3c3c3c] bg-[#000000] text-[10px] font-mono text-[#737373]">
        Evidence is the JPEG produced by the Pi inference pipeline, with its detection boxes already drawn by the model visualizer.
      </div>
    </section>
  );
};
