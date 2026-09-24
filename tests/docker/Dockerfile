# Same immutable Microsoft SDK base used by the nl-dsl-sh interop fixture.
FROM mcr.microsoft.com/dotnet/sdk:8.0@sha256:78235e09001f52b6592c458ac010775ebac6725422e80cd0c1650590f67b2743
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 \
    POWERSHELL_TELEMETRY_OPTOUT=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --no-create-home --home-dir /tmp/paxlet-home paxlet
WORKDIR /workspace
USER paxlet
ENTRYPOINT ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]
