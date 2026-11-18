# Laptop camera sender

`stream_client.py` captures frames from the Fedora laptop webcam and sends them to the AWARESPAN node runtime over WebSocket. It is used by the Fedora-as-Pi evaluation fallback.

Install the repository runtime dependencies from the root (`requirements/runtime.txt`) and use:

```bash
./scripts/fedora.sh run
# In another terminal
./scripts/fedora.sh camera --camera 0 --fps 8
```

The default target is `127.0.0.1:8766`. Use the `--pi-host` and `--pi-port` flags when streaming to a different node. The runtime must be reachable and its ingest endpoint active.
