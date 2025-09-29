
.PHONY: test smoke ci

test:
	python tests/contract_tests.py

smoke:
	SEARCH_PROVIDER=dummy python tests/quick_contract.py

ci:
	python tests/run_all.py


docker-build:
	docker build -t cerberus:local .

docker-run:
	docker run --rm -e SEARCH_PROVIDER=dummy -p 8080:8080 cerberus:local

fly-deploy:
	flyctl deploy --remote-only

fly-status:
	flyctl status
