import { describe, expect, it } from 'vitest';
import { encodeVolunteerFrame } from '../src/services/piClient';

describe('AWSP volunteer media transport', () => {
  it('encodes the JPEG payload using the Python gateway binary framing', () => {
    const jpeg = '\xff\xd8\xff\xd9';
    const buffer = encodeVolunteerFrame({
      type: 'frame',
      frame_id: 0x01020304,
      ts_ms: 1_700_000_000_123,
      jpeg_b64: btoa(jpeg),
    });
    const bytes = new Uint8Array(buffer);
    expect(Array.from(bytes.slice(0, 6))).toEqual([0x41, 0x57, 0x53, 0x50, 0x01, 6]);
    expect(new TextDecoder().decode(bytes.slice(6, 12))).toBe('portal');
    const view = new DataView(buffer);
    let offset = 12;
    expect(view.getUint32(offset, false)).toBe(0x01020304);
    offset += 4;
    expect(Number(view.getBigUint64(offset, false))).toBe(1_700_000_000_123);
    offset += 8;
    expect(view.getUint32(offset, false)).toBe(4);
    offset += 4;
    expect(Array.from(bytes.slice(offset))).toEqual([0xff, 0xd8, 0xff, 0xd9]);
  });
});
