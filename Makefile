.PHONY: check-porcelain clean release-local release test update serve-front serve

NEXT_VERSION = `python -m setuptools_scm --strip-dev`

check-porcelain:
	git diff --exit-code --quiet

clean:
	rm -rf "src.egg-info"
	rm -rf dist
	rm -rf src/vtesrulings/static/dist

release-local: check-porcelain clean
	npm run build
	git tag "${NEXT_VERSION}"
	python -m build

release: release-local
	git push origin "${NEXT_VERSION}"
	twine upload -r test-pypi dist/*
	twine upload dist/*

test:
	black --check src
	ruff check src
	QUART_TESTING=1 pytest -vvs

update:
	npm install --include=dev
	npm update --include=dev
	pip install --upgrade --upgrade-strategy eager -e ".[dev]"

serve-front:
	pm2 --name front start npm -- run front

serve: serve-front
	pm2 --name back start npm -- run back
	pm2 logs
