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
- Verification: Verified by creating a todo for one user and then requesting, updating, and deleting it with a different authenticated user; the API now rejects those requests with `403 Forbidden`.

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
- Verification: Verified by creating a todo with a description and then sending a title update with `completed: false`; the API now preserves the existing description and correctly stores the false completion state.

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
- Verification: Verified by checking the todo list cache key is user-specific and that create/update/delete routes invoke cache invalidation for the authenticated user's todo list keys.

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
- Verification: Verified by exercising the logout cleanup helper to confirm it removes auth tokens, clears localStorage, and flushes the React Query cache, ensuring that stale user and todo data can no longer be rendered or reused across sessions.

## BE-05: Refresh tokens are accepted as valid access tokens on protected routes

- Type: Backend
- Location: `backend/app/api/deps.py` — `get_current_user`; `backend/app/core/security.py` — `verify_token`
- Severity: Critical
- Impact: A valid refresh token can be presented to protected access endpoints and treated as a valid authenticated session because the dependency checks only for a `sub` claim, not the token type. This violates the intended separation between access and refresh tokens.
- Evidence: `verify_token` decodes the JWT and returns the payload without validating that the token is an access token. `get_current_user` only checks whether `payload.get("sub")` exists before loading the user.
- Reproduction:
  1. Log in or register to obtain a refresh token.
  2. Submit that refresh token in the `Authorization: Bearer ...` header to `/api/v1/auth/me` or `/api/v1/todos`.
  3. The request succeeds because `sub` is present and there is no token-type check.
- Fix Proposal: Require `payload.get("type") == "access"` in `get_current_user` and reject refresh tokens with `401 Unauthorized`. Apply the same check anywhere a protected resource depends on an authenticated user.
- Verification: Verified by using a valid refresh token against `/api/v1/auth/me`; the protected route now rejects it with 401 Unauthorized instead of granting access.

## BE-06: Logout is a no-op and does not revoke active sessions

- Type: Backend
- Location: `backend/app/api/v1/auth.py` — `logout`; `backend/app/api/deps.py` — `get_current_user`
- Severity: High
- Impact: The logout endpoint reports success without invalidating or revoking the token in any way. A stolen or reused bearer token remains valid until it expires, which undermines the expected session lifecycle and security guarantees.
- Evidence: `logout()` simply returns `{ "message": "Successfully logged out" }` without storing a revocation record, blacklisting the token, or invalidating the refresh token. The dependency layer accepts the same token afterward because there is no server-side session invalidation.
- Reproduction:
  1. Register or log in to receive an access token.
  2. Call `POST /api/v1/auth/logout` with that token.
  3. Reuse the same bearer token against `/api/v1/auth/me` or `/api/v1/todos`.
  4. The request still succeeds because logout is not revoking the token.
- Fix Proposal: Add server-side token revocation, such as storing the token `jti` or session key in Redis or the database and checking it in `get_current_user`. Rotate or invalidate refresh tokens as part of logout and reject any revoked credential with `401 Unauthorized`.
- Verification: Verified by logging out with an access token and then reusing the same bearer token against `/api/v1/auth/me`; the token is now rejected with 401 Unauthorized.

## FE-02: Protected routes trust localStorage token presence before session validation

-Type: Frontend

- Location: `frontend/src/router/ProtectedRoute.tsx` — `ProtectedRoute`; `frontend/src/features/auth/hooks/useAuth.ts` — `useAuth`
- Severity: Medium
- Impact: `ProtectedRoute` currently grants access to protected routes whenever a non-empty token string exists in `localStorage`, before the session has been validated with the server. An expired, malformed, or otherwise invalid token can therefore cause protected UI to render briefly before the `/auth/me` request fails with `401 Unauthorized`. The response interceptor then clears the session and redirects the user to the login page. The backend still prevents unauthorized access to protected data, so this issue does not allow an expired or invalid token to bypass server-side authorization.
- Evidence: `ProtectedRoute` only checks whether an access token exists. It does not wait for server-side session validation before rendering the protected route. `useAuth` does perform server-side validation through fetchCurrentUser when a token exists: `useQuery({ queryKey: ["currentUser"], ... });`. If the token is expired or invalid, the API returns 401 Unauthorized and the response interceptor clears the token and redirects the user to `/login`.
- Reproduction:
  1. Manually place an expired or invalid JWT string into `localStorage`.
  2. Navigate to a protected route such as the dashboard.
  3. `ProtectedRoute` sees a non-empty token and renders the protected UI immediately.
  4. `useAuth` calls `/auth/me`.
  5. The server rejects the token with `401 Unauthorized`.
  6. The response interceptor clears the session and redirects the user to `/login`.
  7. Observe that protected UI may be rendered briefly before session validation completes.
- Fix Proposal: Treat the presence of a token in `localStorage` as only an initial session hint, not proof of authentication. `ProtectedRoute` should wait for the existing `fetchCurrentUser` session validation to complete before rendering protected content. If the session is invalid, redirect to `/login`. Client-side JWT decoding or expiry validation is not required if `/auth/me` remains the authoritative session validation mechanism.
