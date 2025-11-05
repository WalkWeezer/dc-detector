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
# Ensure legacy plain files are present in dist if Vite didn't bundle them
RUN mkdir -p dist \
  && [ -f app.js ] && [ ! -f dist/app.js ] && cp -f app.js dist/app.js || true \
  && [ -f styles.css ] && [ ! -f dist/styles.css ] && cp -f styles.css dist/styles.css || true \
  && [ -f index.html ] && [ ! -f dist/index.html ] && cp -f index.html dist/index.html || true \
  && [ -f pi.html ] && [ ! -f dist/pi.html ] && cp -f pi.html dist/pi.html || true \
  && [ -f pi.js ] && [ ! -f dist/pi.js ] && cp -f pi.js dist/pi.js || true

FROM nginx:alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
# Nginx config and dev certs (for https access to enable getUserMedia on IP)
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
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


