.PHONY: run test install clean

# The interpreter to use, decided once and by asking rather than by assuming.
#
# `make run` used to be a bare `python -m app.main`, which works on a machine
# where the ambient interpreter happens to have this app's dependencies and
# fails everywhere else -- including on any distribution whose system Python is
# externally managed, where `make install` cannot fix it either because pip
# refuses to write there. The hand-back then names a command that cannot work,
# which is the one thing a generated prototype must not do.
#
# So: use the active environment if it already has what the app needs, and
# otherwise use a local `.venv` that `make` builds on demand. Somebody who has
# activated their own virtualenv gets it; somebody who has not gets a working
# app without having to know that was the question.
PY := $(shell python -c "import textual, sqlalchemy" >/dev/null 2>&1 && echo python || echo .venv/bin/python)

run: $(PY)  ## start the app in this terminal
	$(PY) -m app.main

test: $(PY)  ## run the smoke tests
	$(PY) -m pytest -q

install: ## install what the app needs, into the active environment
	pip install -r requirements.txt

# Built only when `$(PY)` resolved to the local one, because the rule's target
# IS the interpreter path: if the ambient `python` already works, `$(PY)` is
# `python`, no such file rule applies, and nothing is created.
.venv/bin/python: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install --quiet --upgrade pip
	.venv/bin/pip install --quiet -r requirements.txt

clean:   ## throw the database away; the app rebuilds and reseeds it on start
	rm -f *.sqlite3
