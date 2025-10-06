FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 3000
ENV PORT=3000
ENV NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app

CMD ["sh", "-c", "next start -p ${PORT:-3000}"]
