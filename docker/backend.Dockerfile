FROM node:20-bullseye-slim
WORKDIR /app

# Устанавливаем инструменты сборки для нативных модулей (sharp) на ARM
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем только package.json, чтобы не тянуть старый lock с нативными зависимостями (например, canvas)
COPY services/backend/package.json ./
# Разрешаем sharp подтянуть платформенный бинарник (@img/sharp-*)
ENV SHARP_IGNORE_GLOBAL_LIBVIPS=1
RUN npm install --omit=dev --include=optional --no-audit --no-fund && npm cache clean --force

COPY services/backend ./

ENV NODE_ENV=production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD node -e "fetch('http://localhost:8080/health',{keepalive:true}).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
USER node
CMD ["node", "src/server.js"]


