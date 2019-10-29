MAKEFILE := $(abspath $(lastword $(MAKEFILE_LIST)))
ROOT_DIR ?= $(patsubst %/,%,$(dir $(MAKEFILE)))


.PHONY: test
test:
	python setup.py test


.PHONY: coverage
coverage:
	coverage run setup.py test
	coverage report
	coverage xml


.PHONY: lint
lint:
	flake8 kapten --exit-zero


.PHONY: format
format:
	black kapten tests
	autoflake -r -i --remove-all-unused-imports kapten tests
	isort -rc kapten tests


.PHONY: clean
clean:
	rm -rf dist
	rm -rf *.egg-info


.PHONY: publish
publish: clean
	python setup.py sdist bdist_wheel
	python -m twine upload dist/*


.PHONY: requirements
requirements:
	pip-compile \
		--upgrade --pre --generate-hashes \
		--output-file $(ROOT_DIR)/reqs/requirements.txt \
		$(ROOT_DIR)/reqs/requirements.in
	pip-compile \
		--upgrade --pre --generate-hashes \
		--output-file $(ROOT_DIR)/reqs/dev-requirements.txt \
		$(ROOT_DIR)/reqs/dev-requirements.in
	chown \
		--reference $(ROOT_DIR)/reqs/requirements.in \
		$(ROOT_DIR)/reqs/requirements.txt \
		$(ROOT_DIR)/reqs/dev-requirements.txt
