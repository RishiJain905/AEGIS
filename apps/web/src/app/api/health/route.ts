import { WORKSPACE_VERSION } from '@aegis/contracts-ts';
import { NextResponse } from 'next/server';

export function GET() {
  return NextResponse.json({
    status: 'ok',
    service: 'web',
    version: WORKSPACE_VERSION,
  });
}
