FROM braiinssystems/farm-proxy:24.06

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER root

ENTRYPOINT ["/entrypoint.sh"]
