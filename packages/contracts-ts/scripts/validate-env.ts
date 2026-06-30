import { config } from 'dotenv';
import { resolve } from 'node:path';
import { parseAegisEnvironment } from '@aegis/contracts-ts';

config({ path: resolve(process.cwd(), '.env') });

const env = process.env as Record<string, string | undefined>;
const result = parseAegisEnvironment(env);
console.log(
  `Environment valid: ${result.AEGIS_ENV} (API ${String(result.API_PORT)}, WEB ${String(result.WEB_PORT)})`,
);
