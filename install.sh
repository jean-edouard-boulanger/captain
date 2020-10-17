#!/usr/bin/env bash
set -e

CAPTAIN_USER=captain
getent group ${CAPTAIN_USER} >/dev/null 2>&1 || groupadd ${CAPTAIN_USER}
id -u ${CAPTAIN_USER} >/dev/null 2>&1 || useradd -d /home/${CAPTAIN_USER} -g ${CAPTAIN_USER} -m ${CAPTAIN_USER}

python3.8 setup.py build install
mkdir -p /etc/captain/
if [[ ! -f /etc/captain/config.yml ]]
then
  cp captain/server/server-dev.yml /etc/captain/config.yml
fi
cp captain/server/captain-server.service /etc/systemd/system/

cp web/captain-web.service /etc/systemd/system/
WEB_INSTALL_DIR=/usr/local/bin/captain/web
mkdir -p ${WEB_INSTALL_DIR}
cp -r web/* ${WEB_INSTALL_DIR}/
cp -r web/.env ${WEB_INSTALL_DIR}/
cd ${WEB_INSTALL_DIR}/
npm install
npm run build

systemctl daemon-reload
systemctl enable captain-server
systemctl restart captain-server
systemctl enable captain-web
systemctl restart captain-web
