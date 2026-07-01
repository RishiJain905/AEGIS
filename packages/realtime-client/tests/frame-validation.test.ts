import { describe, expect, it } from 'vitest';
import { websocketFrameSchema } from '@aegis/contracts-ts';

describe('websocket frame validation', () => {
  it('accepts subscribed frame fixture shape', () => {
    const frame = {
      schemaVersion: 1,
      protocolVersion: 1,
      messageType: 'subscribed',
      traceId: 'trc_01ARZ3NDEKTSV4RRFFQ69G5FAX',
      sentAt: '2026-06-30T12:00:00.000Z',
      payload: {
        runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
        channel: 'events',
        lastAppliedSequence: 0,
        deliveryMode: 'stream',
      },
    };
    const parsed = websocketFrameSchema.parse(frame);
    expect(parsed.messageType).toBe('subscribed');
  });
});
