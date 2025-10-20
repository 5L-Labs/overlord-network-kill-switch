.DEFAULT_GOAL := all

# deprecated dns_servers, source via envfile
include private/etc/envfile
include private/ghcr_username
VERSION=2.5

check-env-%:
	@ # This code checks if an environment variable is empty
	@ # set ahead of running makefile. i.e. target=blah make check-env-target
	@ if [ "${${*}}" = "" ]; then \
			echo "Environment variable $* not set"; \
			exit 1; \
	fi

clean:
	rm -rf venv/
	find . -name __pycache__ -exec rm -rf {} \;

venv:
	if [ ! -d "venv" ] ; then \
	   uv venv; \
	   source .venv/bin/activate ; \
	   uv pip install -r etc/webserver_requirements.txt ; \
	fi

full: venv
	cp private/etc/config.ini etc/config.ini
	cp private/etc/envfile etc/envfile
	( \
        . .venv/bin/activate; \
    	pyclean .; \
    	podman build -f Containerfile  . \
        -t overlord-dns-admin \
	)

release:
	podman tag localhost/overlord-dns-admin:latest ghcr.io/${RELEASE_USERNAME}/overlord-network-kill-switch:${VERSION}
	podman push ghcr.io/${RELEASE_USERNAME}/overlord-network-kill-switch:${VERSION}

push:
	podman tag localhost/overlord-dns-admin:latest ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}-test
	podman push ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}-test

push-local: check-env-target
	rsync --progress -rv cgi-bin/*.py ${target}:dns_admin/cgi-bin/
	rsync --progress -rv etc/ ${target}:dns_admin/etc/
	ssh ${target} cd dns_admin \&\&

#-v ./cgi-bin/:/opt/webserver/cgi-bin/ -v ./lib/:/opt/webserver/lib/
#  -v ./etc/config.ini:/opt/webserver/etc/config.ini
# --dns=${DNS_SERVERS} # deprecated? podman bug?
TEST_CMD = podman run -d --replace --name=overlord-dns -p 19000:19000 --env-file=./etc/envfile

test-local:
	$(TEST_CMD) localhost/overlord-dns-admin

test-remote:
	podman pull ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}-test
	$(TEST_CMD) ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}-test

test-release:
	podman pull ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}
	$(TEST_CMD) ghcr.io/${GHCR_USERNAME}/overlord-network-kill-switch:${VERSION}

all:
	@echo "No op."
