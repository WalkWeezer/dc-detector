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
# Nginx config and dev certs (for https access to enable getUserMedia on IP)
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/certs/ /etc/nginx/certs/
RUN apk add --no-cache openssl \
  && if [ ! -f /etc/nginx/certs/dev.key ] || [ ! -f /etc/nginx/certs/dev.crt ]; then \
       mkdir -p /etc/nginx/certs \
       && openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout /etc/nginx/certs/dev.key -out /etc/nginx/certs/dev.crt \
            -subj "/CN=localhost"; \
     fi
EXPOSE 80
EXPOSE 443
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1


