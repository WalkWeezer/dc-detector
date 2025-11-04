FROM node:20-alpine AS build
WORKDIR /app

# Устанавливаем только то, что нужно для сборки, затем собираем Vite
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then \
      npm ci --prefer-offline --no-audit --no-fund; \
    else \
      npm install --no-audit --no-fund; \
    fi

# Копируем исходники и собираем
COPY frontend ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1


