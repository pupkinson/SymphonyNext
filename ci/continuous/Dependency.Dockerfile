# Build ONLY from a reviewed source snapshot with the owner-operated setup tool.
# The old one-shot image is a toolchain seed, never rerun as its consumed attempt.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 postgresql \
    && rm -rf /var/lib/apt/lists/*
RUN (getent group 10001 || groupadd --gid 10001 snci-test) \
    && (getent passwd 10001 || useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin snci-test) \
    && chown -R 10001:10001 /seed/home
RUN rm -rf /seed/source && mkdir -p /seed/source && chown 10001:10001 /seed/source
COPY --chown=10001:10001 source/ /seed/source/
USER 10001:10001
ENV HOME=/seed/home MIX_HOME=/seed/home/.mix HEX_HOME=/seed/home/.hex \
    MIX_REBAR3=/usr/local/bin/rebar3 ERL_FLAGS="+S 2:2"
WORKDIR /seed/source/elixir
RUN mix deps.get --check-locked && mix deps.compile \
    && MIX_ENV=test mix deps.compile
USER root
RUN sha256sum /seed/source/elixir/mix.lock | cut -d' ' -f1 > /seed/lock.sha256
USER 10001:10001
WORKDIR /
ENTRYPOINT []
CMD []
