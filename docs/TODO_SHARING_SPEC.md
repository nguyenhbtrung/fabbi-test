# Technical Specification: Todo Sharing

## 1. Overview & Objective

- **Feature Summary**: Allow a todo owner to share a todo list with other authenticated users as either a viewer or editor. Shared users can access the todo according to the permission granted, while the owner retains full control and may revoke access at any time.
- **Problem Statement**: The current application enforces ownership only through `todos.user_id` and does not support collaborative access. A user can only read, update, or delete their own todo records. The feature introduces controlled, time-bounded collaboration without weakening the existing ownership boundary.
- **Target Audience / Roles**:
  - **Owner**: the authenticated user who created the todo and owns the record.
  - **Viewer**: another authenticated user with read-only access to a shared todo.
  - **Editor**: another authenticated user with read and update permissions, but not ownership privileges.
  - **Unauthenticated or unauthorized user**: any user without a valid JWT or without an explicit share grant.

## 2. User Stories & Acceptance Criteria

### User Story 1: Owner shares a todo with another user

- **As a** todo owner
- **I want to** grant another authenticated user either viewer or editor access to one of my todos
- **So that** I can collaborate without transferring ownership
- **Acceptance Criteria**:
  - [ ] The owner can share a todo with a valid user by specifying a target user id and a permission value of `viewer` or `editor`.
  - [ ] A share record is created only when the target user exists and is different from the owner.
  - [ ] The system rejects sharing attempts for the same owner and target user pair with a `400` or `409` response and a clear validation error.
  - [ ] A duplicate share request for the same todo and same target user is rejected as a duplicate/invitable conflict rather than creating a second row.
  - [ ] The new permission becomes effective immediately for subsequent read or write checks.

### User Story 2: Owner revokes sharing access

- **As a** todo owner
- **I want to** revoke a collaborator's access at any time
- **So that** I can maintain control over my todo data
- **Acceptance Criteria**:
  - [ ] The owner can revoke access for a specific user on a specific todo using a dedicated delete action.
  - [ ] The revoke action removes the share record and invalidates any cached todo list data that was previously returned to the affected users.
  - [ ] Immediately after revocation, the previously shared user loses access to the todo; any subsequent read/update/delete request is rejected with a `403` or `404`-equivalent authorization failure.
  - [ ] Revocation does not affect the owner’s ability to access or modify the todo.
  - [ ] Revoked access remains invalid even if the user still has a valid JWT token and previously cached data.

### User Story 3: Viewer reads shared todo content

- **As a** viewer
- **I want to** read a shared todo that I was granted access to
- **So that** I can review the todo without changing it
- **Acceptance Criteria**:
  - [ ] A viewer may read the todo by id when a valid share record exists for the todo and the viewer is the recipient.
  - [ ] A viewer can list the todo if the application exposes shared todo listing or if read permission is checked at route level.
  - [ ] A viewer cannot update the title, description, or completed state.
  - [ ] A viewer cannot delete the todo.
  - [ ] A viewer cannot create, modify, or revoke permissions for that todo.

### User Story 4: Editor updates a shared todo

- **As an** editor
- **I want to** change an authorized todo's content or completed state
- **So that** I can contribute updates without owning the todo
- **Acceptance Criteria**:
  - [ ] An editor may read the todo and update allowed fields using the same schema used for todo updates.
  - [ ] An editor may toggle the `completed` property and update `title` or `description` when the share grant permits modifications.
  - [ ] An editor cannot delete the todo because ownership is still retained by the original user.
  - [ ] An editor cannot re-share the todo with new users or change the existing permission level of other collaborators.
  - [ ] A permission check is enforced on every update request, not only at list time.

### User Story 5: Owner behavior and access control

- **As a** owner
- **I want to** maintain full control over my todo and its sharing permissions
- **So that** no unauthorized user can alter the ownership boundary
- **Acceptance Criteria**:
  - [ ] The owner can read, update, and delete the todo without any share record.
  - [ ] The owner can always access the todo even if permission records are absent or stale.
  - [ ] The owner may revoke access without requiring confirmation from another user.
  - [ ] The owner cannot be restricted from performing normal owner actions by a collaborator’s permission change.

### User Story 6: Unauthorized and invalid access attempts

- **As a** system
- **I want to** reject invalid or unauthorized access requests
- **So that** data isolation remains enforced
- **Acceptance Criteria**:
  - [ ] Requests from users without a valid JWT are rejected with `401 Unauthorized`.
  - [ ] Requests from authenticated users who do not own the todo and do not hold a valid share record are rejected with `403 Forbidden`.
  - [ ] Requests to an unknown todo id return `404 Not Found`.
  - [ ] Requests to share with a non-existent user return `404` or `422` depending on the validation pattern, and the error payload clearly states that the target user does not exist.
  - [ ] Requests attempting to share a todo to a user with a role outside the allowed set are rejected with a validation error.

### User Story 7: Edge cases and concurrency safety

- **As a** product team
- **I want to** handle duplicate and concurrent permission changes safely
- **So that** the system remains stable under realistic usage
- **Acceptance Criteria**:
  - [ ] If a user is already shared to the same todo, a second share request must not create duplicate records.
  - [ ] If permissions are changed concurrently (for example, owner revokes while editor is updating), the next request is evaluated against the latest permission state and is denied when the share record is no longer valid.
  - [ ] If a share is revoked, all cached list data and permission-derived query results are invalidated before the next read is served.
  - [ ] Shared data remains fully isolated by user: one user cannot read or mutate another user’s todo unless explicitly granted.

## 3. Scope

### In-Scope

- Todo sharing between authenticated users.
- Support for `viewer` and `editor` permission levels.
- Owner-only share management and revoke operations.
- Authorization checks for list/read/update/delete operations.
- Data isolation enforcement by user and share record.
- Cache invalidation after share creation, permission update, and revocation.
- Validation and API error handling consistent with the current FastAPI/Pydantic implementation.

### Out-of-Scope

- Shared access to todo collections beyond a single todo record.
- Time-limited or expiring share invitations.
- Role inheritance or admin-managed collaborator permissions.
- Bulk share management across multiple todos in one request.
- Public or anonymous sharing links.
- Notification delivery, email invites, or Slack-style alerts.
- Group-based permissions or teams.
- Permission history/audit log.
- Full sharing UI or dashboard beyond the API contract and backend data model.

## 4. Database Design

### Existing database model in the repository

The current application already contains the following data model:

- `users` table
  - `id` (UUID, PK)
  - `email` (VARCHAR(255), NOT NULL)
  - `hashed_password` (VARCHAR(255), NOT NULL)
  - `created_at` (TIMESTAMPTZ, NOT NULL)
- `todos` table
  - `id` (UUID, PK)
  - `title` (VARCHAR(200), NOT NULL)
  - `description` (TEXT, NULL)
  - `completed` (BOOLEAN, NOT NULL)
  - `user_id` (UUID, FK to `users.id`, NOT NULL)
  - `created_at` (TIMESTAMPTZ, NOT NULL)
  - `updated_at` (TIMESTAMPTZ, NOT NULL)

A todo is currently owned by exactly one user via `todos.user_id`, and the API layer enforces authorization by checking `todo.user_id == current_user.id` before update/delete. This is the existing ownership boundary that sharing must extend without breaking.

### Proposed design for todo sharing

A new table is required to model explicit permissions without changing the meaning of `todos.user_id`.

#### `todo_shares`

| Column                | Type        | Constraints                             | Notes                                                              |
| --------------------- | ----------- | --------------------------------------- | ------------------------------------------------------------------ |
| `id`                  | UUID        | PK, NOT NULL                            | Surrogate primary key for row identity and easier future extension |
| `todo_id`             | UUID        | FK to `todos.id`, NOT NULL              | The todo being shared                                              |
| `owner_user_id`       | UUID        | FK to `users.id`, NOT NULL              | The owner who grants access                                        |
| `shared_with_user_id` | UUID        | FK to `users.id`, NOT NULL              | The recipient of the share                                         |
| `permission`          | VARCHAR(10) | NOT NULL, CHECK in (`viewer`, `editor`) | Access level for the recipient                                     |
| `created_at`          | TIMESTAMPTZ | NOT NULL                                | Record creation time                                               |
| `updated_at`          | TIMESTAMPTZ | NOT NULL                                | Last mutation time                                                 |

#### Constraints

- Primary key: `id`
- Foreign keys:
  - `todo_id` → `todos.id` with `ON DELETE CASCADE`
  - `owner_user_id` → `users.id` with `ON DELETE CASCADE`
  - `shared_with_user_id` → `users.id` with `ON DELETE CASCADE`
- Unique constraint: `UNIQUE (todo_id, shared_with_user_id)`
  - Prevents duplicate share records for the same user on the same todo.
- Check constraint: `permission IN ('viewer', 'editor')`
- Additional business rule: `owner_user_id != shared_with_user_id` must be enforced in application logic before insert/update.

#### Indexes

- `INDEX idx_todo_shares_todo_id (todo_id)`
- `INDEX idx_todo_shares_owner_user_id (owner_user_id)`
- `INDEX idx_todo_shares_shared_with_user_id (shared_with_user_id)`
- `INDEX idx_todo_shares_todo_user (todo_id, shared_with_user_id)`

These indexes support efficient permission queries when checking whether a user is allowed to read or update a todo by looking up `todo_id` and the recipient user id.

### Relationship semantics

- `User` has many `todos` as owner.
- `Todo` belongs to one owner user via `todos.user_id`.
- `Todo` may have many share records through `todo_shares.todo_id`.
- `User` may be the owner of many share grants and may also receive many share grants as collaborator.
- The owner always retains access even when no share record exists.
- A share record represents an explicit grant from owner to recipient; the permission is not inherited and is never assigned to a new owner.

### Proposed migration and design decision

This specification intentionally does not modify the existing `todos.user_id` ownership model. The feature extends the system by adding a separate permissions table instead of reusing `user_id` or changing the meaning of the original owner relationship. This keeps the current architecture compatible with the repository's current `get_owned_todo_or_403` pattern and avoids breaking existing DB logic.

## 5. API Contracts & Endpoints

The repository currently uses authenticated routes under `/api/v1`, JWT-based auth via dependency injection, and FastAPI response models with Pydantic validation. The sharing specification follows the same conventions.

### Endpoint Summary

| Method | Endpoint                                   | Description                                                   | Auth Required |
| ------ | ------------------------------------------ | ------------------------------------------------------------- | ------------- |
| GET    | `/api/v1/todos/{todo_id}/shares`           | List active share grants for a todo owned by the current user | Yes           |
| POST   | `/api/v1/todos/{todo_id}/shares`           | Create or update a share grant for a user on a todo           | Yes           |
| PATCH  | `/api/v1/todos/{todo_id}/shares/{user_id}` | Update an existing share permission                           | Yes           |
| DELETE | `/api/v1/todos/{todo_id}/shares/{user_id}` | Revoke access for a user on a todo                            | Yes           |
| GET    | `/api/v1/todos/shared`                     | List todos visible to the current user through sharing        | Yes           |

### Request and response schema conventions

- All routes require a valid Bearer token via the current `HTTPBearer` dependency.
- Validation follows `pydantic.BaseModel` patterns used by `TodoCreate`, `TodoUpdate`, and `TodoResponse` in the existing backend.
- Response payloads should use `model_config = {"from_attributes": True}` and follow the repository’s pattern of returning object-based JSON responses rather than ad hoc dicts.
- Errors must follow a consistent structure such as `{ "detail": "..." }` or an equivalent validation payload from FastAPI.

### 1) GET `/api/v1/todos/{todo_id}/shares`

- **Authentication requirement**: Required.
- **Authorization requirement**: Only the owner of the todo may list share grants for that todo.
- **Request parameters**: `todo_id` in path; no body.
- **Validation rules**:
  - `todo_id` must be a valid UUID.
  - The todo must exist.
  - The current user must own the todo.
- **Success response**:
  - `200 OK`
  - JSON array or object with active share records: `[{ "todo_id": ..., "shared_with_user_id": ..., "permission": "viewer|editor", "created_at": ..., "updated_at": ... }]`
- **Error response**:
  - `401 Unauthorized` when the JWT is missing or invalid.
  - `403 Forbidden` when current user is not the owner.
  - `404 Not Found` when the todo does not exist.

### 2) POST `/api/v1/todos/{todo_id}/shares`

- **Authentication requirement**: Required.
- **Authorization requirement**: Only the todo owner can create share grants.
- **Request body**:
  ```json
  {
    "shared_with_user_id": "<uuid>",
    "permission": "viewer"
  }
  ```
- **Validation rules**:
  - `shared_with_user_id` must be a valid UUID.
  - `permission` must be one of `viewer` or `editor`.
  - Target user must exist.
  - Target user cannot be the same as the owner.
  - The combination `(todo_id, shared_with_user_id)` must not already exist.
  - The current user must own the todo.
- **Success response**:
  - `201 Created`
  - Returns the newly created share record including `id`, `todo_id`, `shared_with_user_id`, `permission`, `created_at`, `updated_at`.
- **Error response**:
  - `400 Bad Request` for self-share or invalid permission.
  - `401 Unauthorized` for invalid/missing JWT.
  - `403 Forbidden` for non-owner or unauthorized user.
  - `404 Not Found` for missing todo or target user.
  - `409 Conflict` if the share already exists.
  - `422 Unprocessable Entity` for schema validation failures.

### 3) PATCH `/api/v1/todos/{todo_id}/shares/{user_id}`

- **Authentication requirement**: Required.
- **Authorization requirement**: Only the todo owner may modify an existing share record.
- **Request body**:
  ```json
  {
    "permission": "editor"
  }
  ```
- **Validation rules**:
  - `user_id` must be a valid UUID.
  - `permission` must be exactly `viewer` or `editor`.
  - Share record must exist for the given todo and target user.
  - The current user must own the todo.
  - The share target cannot be the owner.
- **Success response**:
  - `200 OK`
  - Returns updated share details.
- **Error response**:
  - `401 Unauthorized` for invalid token.
  - `403 Forbidden` for unauthorized ownership.
  - `404 Not Found` for missing share record or missing todo.
  - `422 Unprocessable Entity` for invalid permission payload.

### 4) DELETE `/api/v1/todos/{todo_id}/shares/{user_id}`

- **Authentication requirement**: Required.
- **Authorization requirement**: Only the todo owner may remove an existing share.
- **Request parameters**:
  - `todo_id` in path
  - `user_id` in path referring to the target collaborator
- **Validation rules**:
  - `user_id` must be a valid UUID.
  - The todo must exist.
  - The current user must own the todo.
  - The share record must exist or the endpoint should treat it as a no-op with `200` or `204` consistently.
- **Success response**:
  - `204 No Content` on successful revocation; or `200 OK` with a confirmation payload if the project prefers explicit responses.
- **Error response**:
  - `401 Unauthorized` for invalid token.
  - `403 Forbidden` for non-owner.
  - `404 Not Found` for missing todo or share record.
- **Important behavior**: After a successful delete, access is revoked immediately for the ended share record. No stale permission may survive the response.

### 5) GET `/api/v1/todos/shared`

- **Authentication requirement**: Required.
- **Authorization requirement**: Any authenticated user may request todos shared to them.
- **Request parameters**: None by default; pagination may be added later if needed.
- **Validation rules**:
  - The current user must be authenticated.
  - Results are filtered to `todo_shares.shared_with_user_id == current_user.id`.
- **Success response**:
  - `200 OK`
  - JSON list or paginated list of shared todos with fields such as `todo_id`, `title`, `owner_user_id`, `permission`, and `updated_at`.
- **Error response**:
  - `401 Unauthorized` if JWT is invalid or missing.
  - `403 Forbidden` only in rare cases when an authenticated user is blocked by a policy layer; otherwise, this endpoint is read-only and should not fail for normal use.

## 6. Business Logic & Security Considerations

### Authorization matrix

| Role            | Read own todo | Update own todo | Delete own todo | Read shared todo | Update shared todo | Delete shared todo | Manage shares |
| --------------- | ------------- | --------------- | --------------- | ---------------- | ------------------ | ------------------ | ------------- |
| Owner           | Yes           | Yes             | Yes             | Yes              | Yes                | Yes                | Yes           |
| Viewer          | No            | No              | No              | Yes              | No                 | No                 | No            |
| Editor          | No            | No              | No              | Yes              | Yes (limited)      | No                 | No            |
| Unauthenticated | No            | No              | No              | No               | No                 | No                 | No            |

### Required permission checks

- All todo read/update/delete requests must validate both ownership and share grants.
- Owner checks continue to be the highest precedence and remain the default path.
- For non-owner requests, the service layer must query `todo_shares` for the current user and the specified `todo_id`.
- If the share record is absent, access is denied.
- If the share record exists with `permission = 'viewer'`, only read access is granted.
- If the share record exists with `permission = 'editor'`, read and update access is granted; delete access remains disallowed unless the user is the owner.

### Self-sharing prevention

- The owner cannot share a todo with themselves.
- The API must reject any share request where `shared_with_user_id == owner_user_id`.
- This rule should be enforced in both the request validation layer and the service layer so the backend cannot be bypassed.

### Duplicate sharing and invite handling

- The app must not create duplicate share rows for the same user and todo.
- Repeating a share request should return either `409 Conflict` or a validation-level error such as `already shared`.
- If an owner wants to change an existing permission, the API should call the update endpoint rather than creating a new row.

### Sharing with non-existent users

- Requests referencing a user id that does not exist must fail with a clear error payload.
- The response should indicate the target user does not exist, not simply a generic 500.

### Unauthorized access and revoked access

- A user without valid share grant and without owner status must receive `403 Forbidden` for any read/update/delete attempt.
- Once revocation occurs, the permission becomes invalid immediately and must not remain effective until a later cache expiry.
- The app should perform permission evaluation at access time, not rely solely on stale cached permission lists.

### Concurrent updates and permission checks

- The permission check must run against current database state at request execution time, not against a stale in-memory representation.
- When an owner revokes access while an editor is already in progress, the next request must be denied if the latest database state no longer contains a valid share record.
- Any update operation must be executed within a transaction when the application performs both the permission lookup and the data mutation.

### Cache invalidation immediately after permission revocation

The repository already uses Redis list-cache invalidation after todo create/update/delete in the existing todo API (`redis.delete_pattern(f"todos:list:{current_user.id}:*")`). The sharing feature must extend this pattern:

- When the owner creates, updates, or revokes a share, invalidate:
  - the owner’s todo list cache for any list that includes their todo data
  - the recipient’s todo list cache for any list that includes shared todos
  - all permission-derived caches if the application caches share results
- The invalidation should be triggered synchronously before returning success to the client, so stale permissions are not served after a revoke.
- Shared todo read/list endpoints must not trust Redis entries beyond the immediate invalidation boundary.

### Data isolation between users

- Users must never see each other’s private todo data without an explicit share grant.
- `GET /api/v1/todos` continues to return only the authenticated user's owned todos unless the API adds a separate shared-todo listing.
- Share-grant lookups must compare `todo_shares.shared_with_user_id` to the authenticated user id and `todo.user_id` to the owner when needed.
- Delete and update endpoints must reject any request where neither ownership nor a valid share record applies.

## 7. Caching & Invalidation Strategy

The current implementation caches authenticated user todo list results in Redis using keys like `todos:list:{user_id}:{page}:{size}`. Sharing should respect this convention and extend the invalidation model.

### Required Redis behavior

- Cache keys for todo list endpoints should remain scoped by user id; for shared data, the key should be derived from the recipient user id and the query parameters used to build the list.
- Ownership changes and permission changes must invalidate all affected cache keys.
- Revocation is a priority invalidation event and must be processed before the API returns a success response.

### Cache invalidation events

1. **Share created**: invalidate owner list cache and recipient list cache if shared-todo queries are cached.
2. **Share permission updated**: invalidate affected owner and recipient lists.
3. **Share revoked**: invalidate owner list cache and any recipient list cache that previously included the todo.
4. **Todo updated or deleted**: invalidate owner list cache and any related shared list caches for users with access.

### Cache safety rule

If a shared user's cache contains a stale todo that was just revoked, the system must treat cache as untrusted until the invalidation step completes. The application should prefer fresh database reads after a permission change to ensure correctness.

## 8. Non-Functional Requirements

- **Security**: permission assertions must be server-side and not based only on front-end UI state.
- **Reliability**: share creation, permission update, and revoke operations must check for the latest DB state before mutating data.
- **Scalability**: share lookup should use an indexed database query to avoid scanning all `todo_shares` rows.
- **Observability**: the service layer should log or capture a structured error when a share grant is rejected due to missing user, permission mismatch, or ownership violation.
- **Compatibility**: the sharing feature must coexist with the existing user and todo models without altering the current semantics of `todos.user_id`.

## 9. Assumptions and Design Decisions

- The original todo ownership model remains intact; the share feature is additive, not a replacement.
- Access is granted at the todo level and not via a separate list-level ownership abstraction.
- Permission values are limited to `viewer` and `editor` for scope control and product simplicity.
- The API returns standard FastAPI-style error payloads and HTTP status codes compatible with the current backend conventions.
- The feature is intentionally scoped to the current product; it does not add email notifications, audit logs, or time-based sharing.
