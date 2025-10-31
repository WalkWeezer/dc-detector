FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || true
COPY frontend ./
RUN npm run build || echo "No build script, using static index.html"

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY --from=build /app/index.html /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1


