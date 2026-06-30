import { z } from 'zod';

import { ContractErrorCode, ContractValidationError } from './errors';

export function parseContract<T extends z.ZodTypeAny>(schema: T, data: unknown): z.infer<T> {
  try {
    // Zod ties parse output to the caller-provided schema generic.
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return -- schema.parse is parameterized by T
    return schema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ContractValidationError({
        code: ContractErrorCode.VALIDATION_FAILED,
        message: 'Contract validation failed',
        details: { errors: error.issues },
      });
    }
    throw error;
  }
}

export function safeParseContract<T extends z.ZodTypeAny>(
  schema: T,
  data: unknown,
): z.SafeParseReturnType<unknown, z.infer<T>> {
  return schema.safeParse(data);
}
