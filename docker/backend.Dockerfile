FROM node:20-bullseye-slim
WORKDIR /app

COPY services/backend/package*.json ./
RUN npm install --omit=dev && npm cache clean --force

COPY services/backend ./
COPY infra/db/migrations ./infra/db/migrations

ENV NODE_ENV=production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD node -e "fetch('http://localhost:8080/health',{keepalive:true}).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
USER node
CMD ["node", "src/server.js"]


