# Tier 1 — Bug Findings

## BE-01: Expired JWT tokens are accepted after expiration

- Type: Backend
- Location: `backend/app/core/security.py` — `verify_token`
- Severity: Critical
- Impact: Expired JWTs are treated as valid tokens, allowing stale sessions to remain active after the expiration time. This is an authentication correctness issue and can extend access beyond the intended session lifetime.
- Evidence: `verify_token` calls `jwt.decode(..., options={"verify_exp": False})`, which disables built-in JWT expiry validation.
- Reproduction:
  1. Generate a token with a negative expiration window.
  2. Send it in an Authorization header to a protected endpoint such as `/api/v1/auth/me`.
  3. The request is accepted instead of failing with `401 Unauthorized`.
- Fix Proposal: Remove the expiry override and allow `jwt.decode` to enforce token expiration. Catch `ExpiredSignatureError` and `JWTError` and return `None` so the endpoint rejects expired or invalid tokens.
- Verification: Verified by generating a JWT token with an expiration time in the past and sending it to protected endpoint `/api/v1/auth/me`; the API now correctly rejects the expired token and returns 401 Unauthorized instead of accepting it.

## BE-02: Cross-user todo access is not restricted by ownership

- Type: Backend
- Location: `backend/app/api/v1/todos.py` — `get_todo`, `update_existing_todo`, `delete_existing_todo`; `backend/app/services/todo_service.py` — `get_todo_by_id`
- Severity: Critical
- Impact: Any authenticated user can read, update, or delete another user’s todo by ID because the server never checks ownership before returning or mutating the record.
- Evidence: `get_todo_by_id` filters only by `Todo.id`. The route handlers use this lookup without verifying `todo.user_id == current_user.id`.
- Reproduction:
  1. User A creates a todo.
  2. User B knows the todo ID and calls `GET`, `PUT`, or `DELETE` on that endpoint.
  3. The API returns or mutates User A’s todo rather than denying access.
- Fix Proposal: After fetching a todo by ID, verify that `todo.user_id == current_user.id`. If not, return `403 Forbidden` or `404 Not Found` consistently and stop the request before mutation or response serialization.

## BE-03: Partial todo updates incorrectly overwrite omitted fields and ignore false boolean values

- Type: Backend

- Location: `backend/app/api/v1/todos.py` — `update_existing_todo`

- Severity: High

- Impact: Partial todo updates do not preserve existing data correctly. In particular, changing completed from true to false is ignored, while omitted optional fields such as description may be overwritten with None. This can leave todo state stale or unintentionally erase existing data.

- Evidence:
  The completed field is only updated when its value is truthy:

  ```python
  if todo_data.completed:
      todo.completed = todo_data.completed
  ```

  Therefore, an explicitly provided completed=false value is ignored.

  Additionally, the code uses:

  ```python
  update_data = todo_data.model_dump()

  if "description" in update_data:
       todo.description = update_data["description"]
  ```

  If `model_dump()` includes unset optional fields with their default None values, an omitted description field is still present in update_data. The code then overwrites the existing description with None.

- Reproduction
  1. Create a todo with completed=true.

  2. Send an update containing: `{"completed": false}`.

  3. Observe that the todo remains `completed=true`.

  4. Create a todo with an existing non-null description.

  5. Send a title-only update without providing description.

  6. Observe that the existing description is overwritten with null.

- Fix Proposal: Use only fields explicitly provided by the client when applying partial updates, for example with: `todo_data.model_dump(exclude_unset=True)` For boolean fields, update the field based on whether it was provided rather than whether its value is truthy. This ensures that explicit false values are persisted while omitted fields remain unchanged.

## BE-04: Todo list cache is not user-scoped and is not invalidated after mutation

- Type: Backend
- Location: `backend/app/api/v1/todos.py` — `list_todos`; `backend/app/core/redis.py` — Redis client
- Severity: High
- Impact: Todo list cache is shared globally rather than scoped by user and request parameters, which allows stale or cross-user data to be served. Cache invalidation is also missing for todo mutations, so old list data remains after updates.
- Evidence: `cache_key = "todos:list"` is used for every request, regardless of user or pagination. Create/update/delete endpoints do not delete the relevant cache entry after changes.
- Reproduction:
  1. User A fetches the todo list and populates the cache.
  2. User B creates or updates a todo.
  3. User A still receives stale list data from Redis.
  4. The same cache key persists even after todo mutation.
- Fix Proposal: Scope Redis keys by authenticated user and query values, for example using user ID and pagination parameters. Invalidate or delete the affected keys after create/update/delete operations so stale cache entries cannot be reused.

## FE-01: Logout leaves stale React Query and session state behind

- Type: Frontend
- Location: `frontend/src/features/auth/api/auth.ts` — `useLogout`; `frontend/src/features/auth/hooks/useAuth.ts` — `useAuth`; `frontend/src/lib/queryClient.ts` — query client configuration
- Severity: High
- Impact: Logging out removes access tokens but leaves React Query state intact, allowing stale user and todo data to remain cached and reused across sessions.
- Evidence: `useLogout` clears localStorage but does not invalidate or clear the React Query cache. `useAuth` keeps `currentUser` in a query keyed only by `['currentUser']` and the app does not clear it on logout.
- Reproduction:
  1. Log in as User A, load the dashboard, and cache the user/todo data.
  2. Log out.
  3. Log in as User B or revisit the app and the stale query state can still be reused in the client despite the token being cleared.
- Fix Proposal: Invalidate and clear the relevant React Query cache during logout, and ensure user-scoped query keys are reset so stale session data cannot remain visible after sign-out.
