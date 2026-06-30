import { WORKSPACE_VERSION } from '@aegis/contracts-ts';

export function formatPlatformStatus(service: string): string {
  return `${service}@${WORKSPACE_VERSION}`;
}

export { WORKSPACE_VERSION };
