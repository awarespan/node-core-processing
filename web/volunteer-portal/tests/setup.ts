import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Web Audio API
class MockAnalyserNode {
  frequencyBinCount = 128;
  fftSize = 256;
  smoothingTimeConstant = 0.5;
  getByteTimeDomainData(array: Uint8Array) {
    for (let i = 0; i < array.length; i++) {
      array[i] = 128 + Math.floor(Math.sin(i) * 30);
    }
  }
  disconnect() {}
}

class MockAudioContext {
  state = 'running';
  createAnalyser() {
    return new MockAnalyserNode();
  }
  createMediaStreamSource() {
    return {
      connect: vi.fn(),
      disconnect: vi.fn(),
    };
  }
  close() {
    this.state = 'closed';
    return Promise.resolve();
  }
}

// @ts-ignore
window.AudioContext = MockAudioContext;
// @ts-ignore
window.webkitAudioContext = MockAudioContext;

// Mock MediaStream and MediaStreamTrack
class MockMediaStreamTrack {
  kind: string;
  enabled: boolean = true;
  readyState: string = 'live';
  onended: (() => void) | null = null;

  constructor(kind: string) {
    this.kind = kind;
  }

  stop() {
    this.readyState = 'ended';
    if (this.onended) this.onended();
  }
}

class MockMediaStream {
  tracks: MockMediaStreamTrack[] = [];

  constructor(tracks: MockMediaStreamTrack[] = []) {
    this.tracks = tracks;
  }

  getTracks() {
    return this.tracks;
  }

  getVideoTracks() {
    return this.tracks.filter((t) => t.kind === 'video');
  }

  getAudioTracks() {
    return this.tracks.filter((t) => t.kind === 'audio');
  }

  addTrack(track: MockMediaStreamTrack) {
    this.tracks.push(track);
  }
}

// @ts-ignore
global.MediaStream = MockMediaStream;

// Mock navigator.mediaDevices
const mockMediaDevices = {
  enumerateDevices: vi.fn().mockResolvedValue([
    { deviceId: 'cam-1', kind: 'videoinput', label: 'FaceTime HD Camera' },
    { deviceId: 'cam-2', kind: 'videoinput', label: 'USB External Webcam' },
    { deviceId: 'mic-1', kind: 'audioinput', label: 'Internal Microphone' },
  ]),
  getUserMedia: vi.fn().mockImplementation((constraints) => {
    const tracks: MockMediaStreamTrack[] = [];
    if (constraints.video) {
      tracks.push(new MockMediaStreamTrack('video'));
    }
    if (constraints.audio) {
      tracks.push(new MockMediaStreamTrack('audio'));
    }
    return Promise.resolve(new MockMediaStream(tracks));
  }),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
};

Object.defineProperty(navigator, 'mediaDevices', {
  value: mockMediaDevices,
  writable: true,
});

// Mock HTMLCanvasElement.toDataURL and getContext
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  drawImage: vi.fn(),
}) as any;

HTMLCanvasElement.prototype.toDataURL = vi.fn().mockReturnValue(
  'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP...'
);
