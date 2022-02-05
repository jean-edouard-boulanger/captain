#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd ${SCRIPT_DIR} && tools/autorestart.sh "captain/" python -m captain.server.main -c captain/server/server-dev.yml
