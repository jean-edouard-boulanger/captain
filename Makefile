run-server:
	python3 -m captain.server.main -c captain/server/server-dev.yml

run-server-dev:
	./tools/autorestart.sh captain/ python3 -m captain.server.main -c captain/server/server-dev.yml

install:
	./install.sh

black:
	black captain/

black-check:
	black --check captain/

isort:
	isort captain/

isort-check:
	isort --check captain/

flake8:
	flake8 captain/

pyupragde:
	git ls-files -- '*.py' | xargs pyupgrade --py311-plus

lint: black-check isort-check flake8
format: pyupragde black isort
