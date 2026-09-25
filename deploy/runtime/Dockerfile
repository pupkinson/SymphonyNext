# Build from repository root. ELIXIR_IMAGE must be an independently resolved
# docker.io/library/elixir:1.19.6-otp-28-slim@sha256:<digest> reference.
# There is deliberately no mutable-tag default.
ARG ELIXIR_IMAGE
FROM ${ELIXIR_IMAGE} AS build
ARG ELIXIR_IMAGE
RUN printf '%s\n' "$ELIXIR_IMAGE" \
    | grep -Ex 'docker[.]io/library/elixir:1[.]19[.]6-otp-28-slim@sha256:[0-9a-f]{64}' >/dev/null

ENV MIX_ENV=prod
WORKDIR /opt/symphony/elixir

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*
RUN mix local.hex 2.2.1 --force
RUN curl --fail --show-error --location \
      https://github.com/erlang/rebar3/releases/download/3.25.1/rebar3 \
      --output /usr/local/bin/rebar3 \
    && echo '924576737f0d3098e1fa4691e6f542bf61036d234c61ebdc18aafef8e2bccf67  /usr/local/bin/rebar3' | sha256sum --check --strict \
    && chmod 0755 /usr/local/bin/rebar3
ENV MIX_REBAR3=/usr/local/bin/rebar3

COPY elixir/mix.exs elixir/mix.lock ./
RUN mix deps.get --check-locked
COPY elixir/config ./config
COPY elixir/lib ./lib
COPY elixir/priv ./priv
RUN mix compile --warnings-as-errors

FROM ${ELIXIR_IMAGE} AS runtime-base
ENV MIX_ENV=prod \
    MIX_HOME=/opt/symphony/mix-home
WORKDIR /opt/symphony/elixir

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 symphony \
    && useradd --uid 10001 --gid 10001 --home-dir /var/lib/symphony --no-create-home symphony \
    && install -d -o 10001 -g 10001 -m 0700 /var/lib/symphony

COPY --from=build /opt/symphony/elixir /opt/symphony/elixir
COPY --from=build /root/.mix /opt/symphony/mix-home
USER 10001:10001

# Use the existing CLI, including its explicit acknowledgement and workflow
# validation. --no-start prevents Mix from starting the scheduler first.
# No shell wrapper, default tracker, credentials, workflow or Codex is installed.
ENTRYPOINT ["mix", "run", "--no-compile", "--no-deps-check", "--no-start", "-e", "SymphonyElixir.CLI.main(System.argv())", "--"]
CMD []

# This target is an explicit offline acceptance fixture, never a deployment.
FROM runtime-base AS smoke
COPY deploy/runtime/smoke.workflow.md /etc/symphony/smoke.workflow.md
CMD ["--i-understand-that-this-will-be-running-without-the-usual-guardrails", "--logs-root", "/var/lib/symphony/log", "/etc/symphony/smoke.workflow.md"]

# The last/default target retains the real CLI admission requirements.
FROM runtime-base AS runtime
ARG SOURCE_COMMIT
RUN printf '%s\n' "$SOURCE_COMMIT" | grep -Ex '[0-9a-f]{40}' >/dev/null
LABEL org.opencontainers.image.source="https://github.com/pupkinson/SymphonyNext" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"
