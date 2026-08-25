"""The front end.

Runs on the host, not in a container: it needs the Docker daemon, the
`proto` code, and the credentials, none of which a generated prototype has.
That asymmetry is the whole reason this is hand-written rather than generated
by proto-pilot itself -- the tool can build the front half of its own UI and
is architecturally forbidden from building the back half.
"""
