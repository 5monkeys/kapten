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
