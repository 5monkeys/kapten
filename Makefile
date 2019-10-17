.PHONY: test
test:
	python setup.py test


.PHONY: coverage
coverage:
	coverage erase; \
	coverage run setup.py test && \
	coverage report \
	 	--skip-covered \
		--show-missing \
		--omit 'venv/*,.eggs/*'


.PHONY: clean
clean:
	rm -rf dist
	rm -rf *.egg-info


.PHONY: publish
publish: clean
	python setup.py sdist bdist_wheel
	python -m twine upload dist/*
