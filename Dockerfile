FROM node:22-bookworm-slim
ARG YOUTUBE=false
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/*
RUN if [ "$YOUTUBE" = true ]; then \
      case "$(uname -m)" in x86_64) asset=yt-dlp_linux;; aarch64) asset=yt-dlp_linux_aarch64;; *) echo 'YouTube image build supports x64/arm64' >&2; exit 1;; esac; \
      mkdir -p /tmp/tesla-ytdlp && cd /tmp/tesla-ytdlp \
      && curl -fsSLO "https://github.com/yt-dlp/yt-dlp/releases/latest/download/$asset" \
      && curl -fsSLO https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS \
      && grep " $asset$" SHA2-256SUMS | sha256sum -c - \
      && install -m 755 "$asset" /opt/yt-dlp && rm -rf /tmp/tesla-ytdlp; \
    fi
WORKDIR /app
COPY stream-lab/*.mjs stream-lab/package.json ./
COPY stream-lab/static ./static
RUN rm -f ./*.test.mjs && mkdir -p /var/lib/tesla-media && chown node:node /var/lib/tesla-media && chmod 700 /var/lib/tesla-media
ENV NODE_ENV=production HOST=0.0.0.0 PORT=8765 DATA_DIR=/var/lib/tesla-media FFMPEG_PATH=/usr/bin/ffmpeg YT_DLP_PATH=/opt/yt-dlp
USER node
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD node -e "fetch('http://127.0.0.1:8765/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "server.mjs"]
