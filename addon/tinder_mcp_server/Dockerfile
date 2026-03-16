FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache git jq bash

# Clone and build the glassbead tinder-mcp-server
RUN git clone https://github.com/glassbead-tc/tinder-mcp-server.git . \
    && npm install \
    && npm run build

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 3000

CMD ["/run.sh"]
