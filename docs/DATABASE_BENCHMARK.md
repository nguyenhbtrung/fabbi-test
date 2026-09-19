# Database Performance Benchmark

## Objective

Tier 3C measures the PostgreSQL access paths used by the todo service on a
large dataset. The goal is to reduce work for user-scoped todo listing and
counting, and to support the `created_at` ordering expected by a paginated todo
list, without adding indexes for query patterns the application does not use.

## Environment

- PostgreSQL: 16.15 (`postgres:16-alpine`)
- Docker Server: 29.8.1
- Host: Linux 7.0.0-31-generic, x86_64
- Users: 10,000
- Todos: 1,000,000
- Benchmark user: `091eb072-21ea-437c-be8b-c9ee576a3a81`
- Todos for benchmark user: 141
- Table size after seeding: 212 MB
- New index size after creation: 39 MB

The dataset was generated with the documented command parameters:

```bash
docker compose run --rm \
  -e SEED_USERS=10000 -e SEED_TODOS=1000000 \
  backend python -m app.db.seed
```

The repository's `docker compose exec` form could not be used while the
backend's normal container was restarting, so the equivalent one-shot `run`
form was used. The seed completed successfully in 72.91 seconds. The seed
script skips todo generation when any todo already exists; the benchmark began
with an empty database and verified the final counts above.

Each query was run three times with `EXPLAIN (ANALYZE, SUMMARY, FORMAT JSON)`.
The table reports the arithmetic mean of PostgreSQL's `Execution Time` values.
The same SQL, parameter, database, and Docker services were used before and
after migration. Cache state was not reset between runs, so these are repeated
warm-up measurements rather than isolated cold-cache measurements. Planning
time and representative scan details are reported separately from the timing
averages.

## Queries

The application query in `app.services.todo_service.get_todos` is equivalent
to:

```sql
SELECT id, title, description, completed, user_id, created_at, updated_at
FROM todos
WHERE user_id = :user_id
OFFSET :skip LIMIT :limit;
```

The service also issues this count query:

```sql
SELECT count(*)
FROM todos
WHERE user_id = :user_id;
```

The current service does not specify an `ORDER BY`. This benchmark additionally
checks the expected ordered-list access pattern because the assessment calls
out ordering by `created_at` and the selected index is intended to support it:

```sql
SELECT id, title, description, completed, user_id, created_at, updated_at
FROM todos
WHERE user_id = :user_id
ORDER BY created_at DESC
LIMIT 20;
```

No current application query filters on `completed`, so no completed-leading
index was added.

## Before Indexing

Only the primary-key indexes existed before the migration. The benchmark user
had 141 todos, while PostgreSQL estimated approximately 100 matching rows.

| Query                 | Average execution time | Representative plan                                    | Observation                                                         |
| --------------------- | ---------------------: | ------------------------------------------------------ | ------------------------------------------------------------------- |
| User-filtered listing |              39.164 ms | Parallel sequential scan                               | Scanned the 1M-row table and removed many non-matching rows.        |
| Ordered listing       |              85.087 ms | Parallel sequential scan + `Gather Merge` + top-N sort | Filtered the table, then sorted matching rows by `created_at DESC`. |
| Count by user         |              80.126 ms | Parallel sequential scan + aggregate                   | Read the table to count 141 matching rows.                          |

The representative first-run plans showed 5,691 shared reads for the
user-filtered listing, a `Gather Merge` and sort for the ordered query, and
15,919 shared reads for the count query. Planning times were 1.201 ms, 0.236
ms, and 0.134 ms respectively in that run.

## Indexing Strategy

Migration `9d5f3e7a1b2c_add_todo_user_created_at_index.py` adds:

```sql
CREATE INDEX ix_todos_user_id_created_at
ON todos (user_id, created_at);
```

The column order puts the equality predicate first, grouping each user's
todos. `created_at` then supplies the ordered traversal within that user's
range. PostgreSQL can scan this ordinary ascending B-tree backward for
`created_at DESC`, so a separate descending index is unnecessary.

This is the minimum justified index:

- It supports the actual `WHERE user_id = ...` listing query.
- It supports the ordered listing without a separate sort.
- It supports the user count through an index-only scan when visibility-map
  coverage permits it.
- It avoids a redundant single-column `user_id` index.
- It excludes `completed` because the current API does not filter by it.

## After Indexing

The representative after-migration plans changed as follows:

- User-filtered listing: `Index Scan using ix_todos_user_id_created_at`.
- Ordered listing: `Index Scan Backward using ix_todos_user_id_created_at`;
  no sort or `Gather Merge` was used.
- Count: `Index Only Scan using ix_todos_user_id_created_at`; heap fetches
  were `0` in the measured plan.

Representative execution times from those plans were 0.302 ms, 0.257 ms, and
0.079 ms. The repeated-run averages used for comparison are below.

## Benchmark Comparison

| Query                 |    Before |    After |        Improvement | Index                         |
| --------------------- | --------: | -------: | -----------------: | ----------------------------- |
| User-filtered listing | 39.164 ms | 0.240 ms | 99.39% (38.923 ms) | `ix_todos_user_id_created_at` |
| Ordered listing       | 85.087 ms | 0.414 ms | 99.51% (84.673 ms) | `ix_todos_user_id_created_at` |
| Count by user         | 80.126 ms | 0.163 ms | 99.80% (79.963 ms) | `ix_todos_user_id_created_at` |

Improvement is calculated as `(before - after) / before * 100`. The measured
plan changes, not only the elapsed times, demonstrate the improvement: full
table scans became targeted index scans, the ordered query lost its sort, and
the count became index-only.

## Index Trade-offs

- **Write latency:** Inserts now maintain one additional B-tree. Updates that
  change `user_id` or `created_at` may also update the index; ordinary updates
  to other columns do not need to change its keys.
- **Storage:** This environment measured approximately 39 MB for the index
  against a 212 MB `todos` table. Production size will vary with UUID and
  timestamp distribution, fill factor, and table growth.
- **Maintenance:** PostgreSQL must vacuum and maintain the additional index.
  It can improve read performance while adding write amplification and vacuum
  work.
- **Migration safety:** The migration is reversible and was validated with a
  downgrade followed by an upgrade. The migration uses normal transactional
  `CREATE INDEX`, which is straightforward but can take a lock on a busy large
  table. For a production-scale live table, schedule the operation or use
  `CREATE INDEX CONCURRENTLY` with the Alembic transaction/autocommit handling
  required by that operation. Concurrent creation takes longer and has its own
  failure-cleanup considerations.
- **Redundancy:** No separate `todos(user_id)` index was added because the
  composite index has `user_id` as its leading column and covers that access
  path.

## Conclusion

On the 10,000-user, 1,000,000-todo dataset, the selected composite index
changed all three benchmarked access paths from parallel sequential scans to
user-targeted index access. The ordered query no longer performs a sort, and
the count used an index-only scan. The result is strong for this selective
user distribution, but timings are environment-specific and cache state was
not isolated. The application still needs an explicit `ORDER BY` if stable
ordering is a product requirement; this Tier 3C change does not alter that
application behavior.
