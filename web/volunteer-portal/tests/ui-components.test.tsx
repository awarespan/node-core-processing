import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VolunteerProvider } from '../src/context/VolunteerContext';
import { StatusBadge } from '../src/components/StatusBadge';
import { Header } from '../src/components/Header';
import { VolunteerControls } from '../src/components/VolunteerControls';
import { OverviewSection } from '../src/components/OverviewSection';
import { PiSpeakerStatusPanel } from '../src/components/PiSpeakerStatusPanel';
import { DetectionEvidence } from '../src/components/DetectionEvidence';

describe('AWARESPAN Volunteer Portal — UI Components Suite', () => {
  it('renders StatusBadge with correct styles and text for all states', () => {
    const { rerender } = render(<StatusBadge state="NOT_CONNECTED" />);
    expect(screen.getByText('IDLE / DISCONNECTED')).toBeInTheDocument();

    rerender(<StatusBadge state="CONNECTING" />);
    expect(screen.getByText('CONNECTING TO PI...')).toBeInTheDocument();

    rerender(<StatusBadge state="CAMERA_CONNECTED" />);
    expect(screen.getByText('CAMERA ACTIVE (PI ACK)')).toBeInTheDocument();

    rerender(<StatusBadge state="MICROPHONE_CONNECTED" />);
    expect(screen.getByText('MIC ACTIVE (PI ACK)')).toBeInTheDocument();

    rerender(<StatusBadge state="BOTH_CONNECTED" />);
    expect(screen.getByText('BOTH SOURCES ACTIVE')).toBeInTheDocument();

    rerender(<StatusBadge state="PERMISSION_DENIED" />);
    expect(screen.getByText('PERMISSION DENIED')).toBeInTheDocument();
  });

  it('renders Header with AWARESPAN wordmark and action buttons', () => {
    const onOpenAuth = vi.fn();
    const onOpenConfig = vi.fn();
    const onOpenDocs = vi.fn();

    render(
      <VolunteerProvider>
        <Header
          onOpenAuth={onOpenAuth}
          onOpenConfig={onOpenConfig}
          onOpenDocs={onOpenDocs}
        />
      </VolunteerProvider>
    );

    expect(screen.getByText('AWARESPAN')).toBeInTheDocument();
    expect(screen.getByText('AUTHENTICATE')).toBeInTheDocument();

    fireEvent.click(screen.getByText('AUTHENTICATE'));
    expect(onOpenAuth).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('CONTRACT'));
    expect(onOpenDocs).toHaveBeenCalledTimes(1);
  });

  it('renders VolunteerControls with 3 segmented mode buttons', () => {
    vi.stubEnv('VITE_MOCK_MODE', 'false');
    render(
      <VolunteerProvider>
        <VolunteerControls onOpenAuthPrompt={vi.fn()} />
      </VolunteerProvider>
    );

    expect(screen.getByText('01 // Camera')).toBeInTheDocument();
    expect(screen.getByText('02 // Microphone')).toBeInTheDocument();
    expect(screen.getByText('03 // Both Sources')).toBeInTheDocument();
    expect(screen.getByText('START VOLUNTEERING NOW')).toBeInTheDocument();

    // The live portal fails closed until the Pi advertises an audio input path.
    expect(screen.getByText(/Audio donation is locked/i)).toBeInTheDocument();
    expect(screen.getByText('02 // Microphone').closest('button')).toBeDisabled();
    fireEvent.click(screen.getByText('01 // Camera'));
    expect(screen.getByText('Target Video Camera')).toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it('renders OverviewSection with node ID and target URL', () => {
    render(
      <VolunteerProvider>
        <OverviewSection />
      </VolunteerProvider>
    );

    expect(screen.getByText('TARGET RASPBERRY PI EDGE NODE')).toBeInTheDocument();
    expect(screen.getByText('Probe Node Health')).toBeInTheDocument();
    expect(screen.getByText('NODE STATUS')).toBeInTheDocument();
  });

  it('renders the Pi-owned audio hardware status without browser playback controls', () => {
    render(
      <VolunteerProvider>
        <PiSpeakerStatusPanel />
      </VolunteerProvider>
    );
    expect(screen.getByText('PI AUDIO HARDWARE OWNERSHIP')).toBeInTheDocument();
    expect(screen.getByText(/Waiting for the Pi to report audio capabilities/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /play deterrence tone/i })).not.toBeInTheDocument();
  });

  it('renders the Pi detection evidence area before the first detection', () => {
    render(
      <VolunteerProvider>
        <DetectionEvidence />
      </VolunteerProvider>
    );
    expect(screen.getByText('DETECTION EVIDENCE')).toBeInTheDocument();
    expect(screen.getByText('No detections received yet.')).toBeInTheDocument();
  });

});
