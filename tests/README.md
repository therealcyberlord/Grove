# Grove Tests

Two test suites, both run with the same command:

```bash
PYTHONPATH=. uv run pytest tests/ -v
```

## Suites

### `tests/scorers/` — Deterministic scorer unit tests

Tests for the rule-based eval scorers. No API keys or external services needed — pure Python logic only.

| File | What it tests |
|---|---|
| `test_routing.py` | `score_routing` — Jaccard similarity of subagent detection |
| `test_structure.py` | `score_structure` — required/forbidden section header checks |
| `test_urls.py` | `score_no_fabricated_urls` — all report URLs must come from tool results |

### `tests/db/` — Database and storage integration tests

Tests for the PostgreSQL persistence layer. Requires a running PostgreSQL instance pointed to by `TEST_DATABASE_URL`.

| File | What it tests |
|---|---|
| `test_filings_agent.py` | `_do_fetch_and_index` DB cache hit, stale refetch, S3 key persistence |
| `test_pageindex_client.py` | `DBBackedPageIndexClient` — persist to DB, hydrate from DB, cold-start sync |
| `test_seed.py` | `seed_db.py` — filing and page index seeding logic |

## Database setup for `tests/db/`

Tests run against a dedicated `TEST_DATABASE_URL` database (default: `grovedb_test`) to avoid touching production data in `grovedb`.

```bash
createdb grovedb_test
psql -d grovedb_test -c "GRANT ALL ON SCHEMA public TO <your_user>;"
```

Add to `.env`:
```
TEST_DATABASE_URL=postgresql://<user>:<password>@localhost:5432/grovedb_test
```

## Isolation pattern

The `db_session` fixture follows the SQLAlchemy-recommended pattern for test suites: each test runs inside a transaction that is rolled back on teardown using `join_transaction_mode="create_savepoint"`. The session is bound to a connection with an open outer transaction, so any `session.commit()` calls inside production code only release a savepoint — the outer transaction is always rolled back. No test data ever persists to the database.

`patch_db` extends this by patching `clients.database.get_db_session` to yield the test session, so production code under test uses the same in-transaction session.
