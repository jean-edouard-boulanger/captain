run-server-dev:
	./tools/autorestart.sh captain/ python3 -m captain.server.main -c captain/server/server-dev.yml

install:
	./install.sh
