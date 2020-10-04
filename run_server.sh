#!/usr/bin/env bash
handler()
{
  echo
  echo "killing server"
  kill -9 "${pid}"
  echo "done"
}
trap handler SIGINT
export PYTHONWARNINGS="ignore:Unverified HTTPS request"
python3.8 -m captain.server.main -c captain/server/server-dev.yml &
pid=$!
wait ${pid}
