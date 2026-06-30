import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { FIXTURE_SCHEMA_MAP, parseContract } from '../src/index';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.resolve(testDir, '../../../tests/contract/fixtures/valid');

describe('cross-language round-trip', () => {
  for (const fixtureName of Object.keys(FIXTURE_SCHEMA_MAP)) {
    it(`round-trips ${fixtureName}.json`, () => {
      const fixturePath = path.join(fixturesDir, `${fixtureName}.json`);
      const original = JSON.parse(readFileSync(fixturePath, 'utf-8')) as unknown;
      const schema = FIXTURE_SCHEMA_MAP[fixtureName as keyof typeof FIXTURE_SCHEMA_MAP];
      const parsed = parseContract(schema, original);
      const serialized = JSON.parse(JSON.stringify(parsed)) as unknown;
      const reparsed = parseContract(schema, serialized);
      expect(reparsed).toEqual(serialized);
    });
  }
});
