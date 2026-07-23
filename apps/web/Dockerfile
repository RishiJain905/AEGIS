# syntax=docker/dockerfile:1

FROM node:22.15.1-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc turbo.json ./
COPY config/tsconfig.base.json config/
COPY apps/web/package.json apps/web/
COPY packages/contracts-ts/package.json packages/contracts-ts/
COPY packages/ui/package.json packages/ui/
RUN pnpm install --frozen-lockfile

FROM node:22.15.1-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/v1/realtime
# NEXT_PUBLIC_* vars are inlined at build time, so the data source must be baked
# here (compose runtime env cannot change it). Default to the API-backed client
# so images never ship the fixture dataset.
ARG NEXT_PUBLIC_AEGIS_DATA_SOURCE=api
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_AEGIS_DATA_SOURCE=$NEXT_PUBLIC_AEGIS_DATA_SOURCE
RUN pnpm --filter @aegis/web build

FROM node:22.15.1-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    HOME=/tmp \
    TMPDIR=/tmp \
    NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S aegis && adduser -S aegis -G aegis
RUN apk upgrade --no-cache
COPY --from=builder --chown=aegis:aegis /app/apps/web/.next/standalone ./
COPY --from=builder --chown=aegis:aegis /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=aegis:aegis /app/apps/web/public ./apps/web/public
USER aegis
EXPOSE 3000
ENV WEB_PORT=3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["node", "apps/web/server.js"]
