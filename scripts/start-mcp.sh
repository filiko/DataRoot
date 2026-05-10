#!/bin/bash
# Launcher for the DataRoot MCP stdio server. Used by Codex via wsl.exe.
# Keep this script tiny and silent on stdout — anything that prints to stdout
# before the MCP handshake will corrupt JSON-RPC framing.
set -e
cd /mnt/c/Users/ajfil/Documents/Github/DataRoot
source ~/.venvs/dataroot/bin/activate >/dev/null
set -a
source .env
set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH=src
export MIRO_BOARD_ID="${MIRO_BOARD_ID:-uXjVHVqV-rs=}"
export DATAROOT_LINK_ADDRESS_JOIN=1
exec python -m dataroot.mcp
