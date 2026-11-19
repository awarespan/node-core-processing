# Linux workstation webcam sender

The laptop sender streams a local webcam into the node runtime over its WebSocket ingest endpoint. Prepare the host with `./scripts/setup.sh --profile linux`, start the node runtime, then in a second terminal run:

```bash
.venv/bin/python laptop/stream_client.py --pi-host 127.0.0.1 --pi-port 8766 --camera 0 --fps 8
```

For a runtime on another trusted LAN host, replace `127.0.0.1` with that host's LAN IP. Do not expose the ingest port to the public internet.
