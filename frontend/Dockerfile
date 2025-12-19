# Build stage
FROM oven/bun:latest AS build-stage
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install
COPY . .
# Set build-time argument for WS URL if needed
ARG VITE_WS_URL
ENV VITE_WS_URL=$VITE_WS_URL
RUN bun run build

# Production stage
FROM nginx:stable-alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
