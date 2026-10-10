FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ .
RUN useradd -r -u 10001 bpn && mkdir /data && chown bpn /data
USER bpn
ENV BPN_DB_PATH=/data/bpn.sqlite3
EXPOSE 8460
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8460/health')"
CMD ["uvicorn", "--factory", "bpn.app:get_app", "--host", "0.0.0.0", "--port", "8460"]
