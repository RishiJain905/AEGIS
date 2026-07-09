'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  approveProposalResponseSchema,
  modifyProposalResponseSchema,
  parseContract,
  rejectProposalResponseSchema,
  type ApproveProposalRequestV1,
  type ApproveProposalResponseV1,
  type ModifyProposalRequestV1,
  type ModifyProposalResponseV1,
  type RejectProposalRequestV1,
  type RejectProposalResponseV1,
} from '@aegis/contracts-ts';

import { queryKeys } from '@/lib/api/query-keys';
import { ApiClientError } from '@/lib/api/types';

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
}

export function newApprovalIdempotencyKey(prefix: string): string {
  return `${prefix}-${String(Date.now())}-${Math.random().toString(36).slice(2, 10)}`;
}

async function postApprovalJson<T>(
  path: string,
  body: unknown,
  parser: (data: unknown) => T,
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Actor-Id': 'asset:operator-console',
      Authorization: 'Bearer synthetic-operator-token',
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let envelope;
    try {
      envelope = (await response.json()) as {
        code?: string;
        message?: string;
        traceId?: string;
      };
    } catch {
      throw new ApiClientError({
        code: 'HTTP_ERROR',
        message: `Request failed with status ${String(response.status)}`,
        status: response.status,
      });
    }
    throw new ApiClientError({
      code: envelope.code ?? 'HTTP_ERROR',
      message: envelope.message ?? 'Approval workflow request failed',
      status: response.status,
      traceId: envelope.traceId,
    });
  }
  const data: unknown = await response.json();
  return parser(data);
}

export function useApprovalMutations(incidentId: string) {
  const queryClient = useQueryClient();

  const invalidate = async () => {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.incidents.investigation(incidentId),
    });
  };

  const approve = useMutation({
    mutationFn: (request: ApproveProposalRequestV1): Promise<ApproveProposalResponseV1> =>
      postApprovalJson(`/api/v1/action-proposals/${request.proposalId}/approve`, request, (data) =>
        parseContract(approveProposalResponseSchema, data),
      ),
    onSuccess: () => void invalidate(),
  });

  const reject = useMutation({
    mutationFn: (request: RejectProposalRequestV1): Promise<RejectProposalResponseV1> =>
      postApprovalJson(`/api/v1/action-proposals/${request.proposalId}/reject`, request, (data) =>
        parseContract(rejectProposalResponseSchema, data),
      ),
    onSuccess: () => void invalidate(),
  });

  const modify = useMutation({
    mutationFn: (request: ModifyProposalRequestV1): Promise<ModifyProposalResponseV1> =>
      postApprovalJson(`/api/v1/action-proposals/${request.proposalId}/modify`, request, (data) =>
        parseContract(modifyProposalResponseSchema, data),
      ),
    onSuccess: () => void invalidate(),
  });

  return { approve, reject, modify };
}
