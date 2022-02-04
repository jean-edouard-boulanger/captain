#!/usr/bin/env bash
set -e

if [[ "$EUID" -ne 0 ]]
  then echo "Please run as root: sudo make install"
  exit
fi

captain_user=captain
echo "creating '${captain_user}' user (if needed)"
getent group ${captain_user} >/dev/null 2>&1 || groupadd ${captain_user}
id -u ${captain_user} >/dev/null 2>&1 || useradd -d /home/${captain_user} -g ${captain_user} -m ${captain_user}

set +e
echo "stopping running captain services (if running)"
systemctl stop captain >/dev/null 2>&1
set -e

captain_dir=/usr/local/bin/captain
echo "removing previous captain installation"
rm -rf ${captain_dir}
mkdir -p ${captain_dir}

captain_server_dir="${captain_dir}/server"
echo "installing captain server"
mkdir -p ${captain_server_dir}
python3.9 -m venv ${captain_server_dir}/venv/
venv_python=${captain_server_dir}/venv/bin/python
${venv_python} -m pip install --upgrade pip
${venv_python} -m pip install -r requirements.txt
${venv_python} setup.py build install

captain_web_dir="${captain_dir}/web"
echo "installing captain web application"
mkdir -p ${captain_web_dir}
cp -r web/src/ web/public/ web/.env web/package.json web/package-lock.json web/run-prod.sh ${captain_web_dir}/
(cd ${captain_web_dir} && npm install)
(cd ${captain_web_dir} && npm run build)

captain_conf_dir=/etc/captain
mkdir -p ${captain_conf_dir}
if [[ ! -f "${captain_conf_dir}/config.yml" ]]
then
  echo "copying captain default configuration to ${captain_conf_dir}"
  cp captain/server/server-dev.yml ${captain_conf_dir}/config.yml
fi

cp captain/server/captain-server.service /etc/systemd/system/
cp web/captain-web.service /etc/systemd/system/
cp captain.service /etc/systemd/system

systemctl daemon-reload
systemctl enable captain captain-web captain-server
systemctl start captain
