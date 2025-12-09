# Frontend Dockerfile
FROM node:18-alpine as build

WORKDIR /app

# Копирование package files
COPY package*.json ./
RUN npm ci

# Копирование кода и сборка
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
