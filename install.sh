#!/usr/bin/env bash
set -e

CAPTAIN_USER=captain
getent group ${CAPTAIN_USER} >/dev/null 2>&1 || groupadd ${CAPTAIN_USER}
id -u ${CAPTAIN_USER} >/dev/null 2>&1 || useradd -d /home/${CAPTAIN_USER} -g ${CAPTAIN_USER} -m ${CAPTAIN_USER}

python3.8 setup.py build install
mkdir -p /etc/captain/
cp captain/server/server-dev.yml /etc/captain/config.yml
cp captain/server/captain-server.service /etc/systemd/system/

cp web/captain-web.service /etc/systemd/system/
WEB_INSTALL_DIR=/usr/local/bin/captain/web
mkdir -p ${WEB_INSTALL_DIR}
cp -r web/* ${WEB_INSTALL_DIR}/
npm run build
