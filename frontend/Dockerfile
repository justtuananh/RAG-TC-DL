FROM node:24-slim AS build
WORKDIR /app
COPY package*.json ./
# package-lock.json được ghi bằng npm 11; npm 10 của node:20 đọc peer tùy chọn esbuild của
# vite lồng trong vitest thành phụ thuộc thiếu nên `npm ci` từ chối lock.
RUN npm install -g npm@11 && npm ci
COPY . .
RUN npm run typecheck && npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
