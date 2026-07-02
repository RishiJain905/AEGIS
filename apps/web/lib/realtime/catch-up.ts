import type { DomainEventEnvelopeV1 } from '@aegis/contracts-ts';
import { domainEventEnvelopeSchema, parseContract } from '@aegis/contracts-ts';

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
}

export async function fetchRunEvents(
  runId: string,
  fromSequence: number,
  signal?: AbortSignal,
): Promise<DomainEventEnvelopeV1[]> {
  const params = new URLSearchParams({
    from_sequence: String(fromSequence),
    limit: '500',
  });
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/realtime/runs/${runId}/events?${params.toString()}`,
    {
      signal,
      headers: { Accept: 'application/json' },
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch run events: ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  if (
    typeof body !== 'object' ||
    body === null ||
    !('events' in body) ||
    !Array.isArray((body as { events: unknown }).events)
  ) {
    throw new Error('Invalid run events response');
  }
  return (body as { events: unknown[] }).events.map((event) =>
    parseContract(domainEventEnvelopeSchema, event),
  );
}

export async function fetchMissingEvents(
  runId: string,
  fromSequence: number,
  toSequence: number,
  signal?: AbortSignal,
): Promise<DomainEventEnvelopeV1[]> {
  const events = await fetchRunEvents(runId, fromSequence, signal);
  return events.filter((event) => event.sequence <= toSequence);
}
