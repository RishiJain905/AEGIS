import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import {
  ContractErrorCode,
  ContractValidationError,
  assertSupportedSchemaVersion,
  graphNodeSchema,
  parseContract,
  runSchema,
  safeParseContract,
} from '../src/index';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const invalidDir = path.resolve(testDir, '../../../tests/contract/fixtures/invalid');

function readInvalidFixture(name: string): unknown {
  return JSON.parse(readFileSync(path.join(invalidDir, name), 'utf-8')) as unknown;
}

describe('invalid fixtures', () => {
  it('rejects unknown schema version', () => {
    const payload = readInvalidFixture('unknown_schema_version.json');
    const result = safeParseContract(graphNodeSchema, payload);
    expect(result.success).toBe(false);
  });

  it('rejects invalid asset id', () => {
    const payload = readInvalidFixture('invalid_asset_id.json');
    expect(() => parseContract(graphNodeSchema, payload)).toThrow(ContractValidationError);
  });

  it('rejects missing required field', () => {
    const payload = readInvalidFixture('missing_required_field.json');
    const result = safeParseContract(graphNodeSchema, payload);
    expect(result.success).toBe(false);
  });

  it('rejects invalid timestamp', () => {
    const payload = readInvalidFixture('invalid_timestamp.json');
    const result = safeParseContract(runSchema, payload);
    expect(result.success).toBe(false);
  });

  it('assertSupportedSchemaVersion rejects unsupported versions', () => {
    expect(() => {
      assertSupportedSchemaVersion('graph_node', 99);
    }).toThrow(ContractValidationError);
    try {
      assertSupportedSchemaVersion('graph_node', 99);
    } catch (error) {
      expect(error).toBeInstanceOf(ContractValidationError);
      if (error instanceof ContractValidationError) {
        expect(error.code).toBe(ContractErrorCode.SCHEMA_VERSION_UNSUPPORTED);
      }
    }
  });
});
