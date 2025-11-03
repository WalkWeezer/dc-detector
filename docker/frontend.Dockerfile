FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || true
COPY frontend ./
RUN npm run build || echo "No build script, using static index.html"

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY --from=build /app/index.html /usr/share/nginx/html/
# Fallback static assets when there's no build step
COPY --from=build /app/app.js /usr/share/nginx/html/
COPY --from=build /app/styles.css /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1


