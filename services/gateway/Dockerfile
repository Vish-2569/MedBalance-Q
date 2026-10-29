FROM node:22-alpine AS web-build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/index.html web/vite.config.ts web/tsconfig.json web/tsconfig.app.json web/tsconfig.node.json ./
COPY web/src ./src
COPY web/public ./public
RUN npm run build

FROM nginx:alpine
COPY services/gateway/nginx.conf /etc/nginx/nginx.conf
COPY --from=web-build /app/dist /usr/share/nginx/html
