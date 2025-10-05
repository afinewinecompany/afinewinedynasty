FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npm run build

EXPOSE 3000
ENV PORT=3000

CMD ["sh", "-c", "next start -p ${PORT:-3000}"]
