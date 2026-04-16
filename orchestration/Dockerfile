FROM python:3.11-slim

WORKDIR /opt/dagster/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY shared /opt/shared
RUN pip install --no-cache-dir -e /opt/shared

COPY orchestration/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY orchestration/ /opt/dagster/app/orchestration/
COPY orchestration/workspace.yaml /opt/dagster/app/workspace.yaml

ENV DAGSTER_HOME=/opt/dagster/dagster_home
RUN mkdir -p $DAGSTER_HOME
COPY orchestration/dagster.yaml $DAGSTER_HOME/dagster.yaml

EXPOSE 3000
