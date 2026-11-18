# Operator scripts

Run scripts from any working directory; each resolves the repository root itself.

| Script | Purpose | Target |
|---|---|---|
| `install.sh` | Install production dependencies and systemd services | Raspberry Pi OS |
| `fedora.sh setup` | Prepare a local Python environment | Fedora workstation |
| `fedora.sh run` | Run the node runtime locally without systemd | Fedora workstation |
| `fedora.sh test` | Run the automated test suite | Fedora workstation |
| `fedora.sh models` | Verify model artifacts and run CPU inference smoke tests | Fedora workstation |
| `status.sh` | Inspect installed services and node health | Raspberry Pi |
| `update.sh` / `rollback.sh` | Manage a deployed node revision | Raspberry Pi |
| `uninstall.sh` | Remove deployed services (optional `--purge`) | Raspberry Pi |

Specialist tools live outside the normal operator surface: `pi/setup-ap.sh`, `tools/deploy_frontend.sh`, `tools/provision_totp.py`, `scripts/evaluation_demo.py`, and `ml_pipeline/tools/`.
