ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Home Assistant base images don't include Node.js/npm.
# Install Node.js tooling + minimal build deps.
RUN apk add --no-cache \
    bash \
    git \
    jq \
    nodejs \
    npm \
    python3 \
    make \
    g++

# Clone and build the glassbead tinder-mcp-server
RUN git clone https://github.com/glassbead-tc/tinder-mcp-server.git . \
    && npm install \
    && npm run build

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 3000

CMD ["/run.sh"]
