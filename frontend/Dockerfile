FROM node:18-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:18-alpine AS builder
WORKDIR /app
ENV NODE_PATH=/app/src
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
ENV NODE_ENV=production
ENV PORT=3100
ENV NODE_PATH=/app/src
WORKDIR /app
# Install curl for healthcheck
RUN apk add --no-cache curl
COPY --from=builder /app .
EXPOSE $PORT
CMD ["sh", "-c", "npm run start"]
