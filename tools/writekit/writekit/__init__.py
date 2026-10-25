"""
What every writer shares. A writer is the one process that changes one database; the read
API only reads. tools/career and tools/networking are writers. How to add one: docs/writers.md.

    db.py       Database: reading, one-transaction changes with a backup, old backups thinned, migrations
    app.py      create_writer(): the write header, the size limit, idempotency keys, migrations on start, errors
    identity.py the tailnet check: only your logins, over the tailnet; the read API uses it too
    errors.py   Refused, NotFound, Rejected, and the HTTP status of each
    forms.py    Form for request bodies; Line and Long text, with a blank as nothing
    testing.py  HEADERS for test clients, and the schema-is-current check
    env.py      env_value(): a setting from the checkout's .env; load_api_key(), for a writer that calls Claude
    files.py    file_in(): a file a request names, right in its folder, never through a link out of it
    career.py   where career's files are, and the largest draft, for the career writer and the read API
"""
