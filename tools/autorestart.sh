#!/usr/bin/env bash
sigint_handler() {
  if [[ -n "${PID}" ]]
  then
    kill -9 "${PID}"
  fi
  exit
}

trap sigint_handler SIGINT

watched="${1}"
shift

echo "watching directory: ${watched}"
while true
do
  echo "running: ${*}"
  "$@" &
  app_pid=${!}
  if [[ "$(uname)" == "Darwin" ]]
  then
    fswatch -1 -r "${watched}"
  else
    inotifywait -e modify -e move -e create -e delete -e attrib -r "${watched}"
  fi
  echo "changes detected, restarting ..."
  kill -9 "${app_pid}"
done
