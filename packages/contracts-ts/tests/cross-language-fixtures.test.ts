import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { FIXTURE_SCHEMA_MAP, parseContract } from '../src/index';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.resolve(testDir, '../../../tests/contract/fixtures/valid');

describe('cross-language valid fixtures', () => {
  for (const fixtureName of Object.keys(FIXTURE_SCHEMA_MAP)) {
    it(`parses ${fixtureName}.json`, () => {
      const fixturePath = path.join(fixturesDir, `${fixtureName}.json`);
      const payload = JSON.parse(readFileSync(fixturePath, 'utf-8')) as unknown;
      const schema = FIXTURE_SCHEMA_MAP[fixtureName as keyof typeof FIXTURE_SCHEMA_MAP];
      const parsed = parseContract(schema, payload);
      expect(parsed).toBeDefined();
    });
  }

  it('has a fixture file for every mapped contract', () => {
    const files = new Set(
      readdirSync(fixturesDir)
        .filter((name) => name.endsWith('.json'))
        .map((name) => name.replace(/\.json$/, '')),
    );
    for (const fixtureName of Object.keys(FIXTURE_SCHEMA_MAP)) {
      expect(files.has(fixtureName)).toBe(true);
    }
  });
});
