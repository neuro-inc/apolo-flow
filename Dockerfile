FROM python:3.14-bookworm AS requirements

ARG APOLO_FLOW_DIST

ENV PATH=/root/.local/bin:$PATH

RUN pip install --user --upgrade pip

ADD ./dist /dist

RUN pip install --user "/${APOLO_FLOW_DIST}"


FROM python:3.14-bookworm

LABEL org.opencontainers.image.source="https://github.com/neuro-inc/neuro-flow"

COPY --from=requirements /root/.local /root/.local
COPY docker.entrypoint.sh /var/lib/apolo/entrypoint.sh
RUN chmod u+x /var/lib/apolo/entrypoint.sh

WORKDIR /root
ENV PATH=/root/.local/bin:$PATH

ENTRYPOINT ["/var/lib/apolo/entrypoint.sh"]
