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
	black kapten
	isort -rc kapten


.PHONY: clean
clean:
	rm -rf dist
	rm -rf *.egg-info


.PHONY: publish
publish: clean
	python setup.py sdist bdist_wheel
	python -m twine upload dist/*
