.PHONY: run test install clean

run:     ## start the app in this terminal
	python -m app.main

test:    ## run the smoke tests
	python -m pytest -q

install: ## install what the app needs, into the active environment
	pip install -r requirements.txt

clean:   ## throw the database away; the app rebuilds and reseeds it on start
	rm -f *.sqlite3
