# Manual Test Plan: Authentication, Authorization, and Todo Security

## 1. Scope & Objective

- Objective of testing: validate authentication flows, access control, and todo logic in the real application.
- Scope of testing: Authentication, Authorization, Todo CRUD, Cache invalidation, Cross-user data isolation.
- Do not rely on mocks or synthetic data for evaluation; testing is performed against the running application in the development environment.

## 2. Test Environment & Prerequisites

- Backend Base URL: `http://localhost:8000`
- Frontend Base URL: `http://localhost:5173`
- Pre-seeded Test Accounts:
  - Account 1 (User A): `user_a@test.com` / `Password@123`
  - Account 2 (User B): `user_b@test.com` / `Password@123`
- Prerequisites:
  - Backend service running and healthy.
  - Frontend service reachable.
  - Database initialized and seeded with the required users.
  - Redis available and cache enabled.

## 3. Test Cases Matrix

| TC ID | Module / Feature          | Test Scenario                                                            | Preconditions                                              | Test Steps                                                                                                                                      | Expected Result                                                                                                                                          | Priority / Severity | Status  |
| ----- | ------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ------- |
| TC-01 | Auth                      | Successful login with correct password                                   | User A exists in the system                                | 1. Open the login page.<br>2. Enter the correct email and password.<br>3. Click Sign In.                                                        | User is redirected to the dashboard/todo page; token is stored; no error is shown.                                                                       | High / Blocker      | Pending |
| TC-02 | Auth                      | Failed login with incorrect password                                     | User A exists in the system                                | 1. Open the login page.<br>2. Enter a valid email and an incorrect password.<br>3. Click Sign In.                                               | The system returns a generic error such as "Invalid email or password"; no sensitive information is exposed; user remains on the login page.             | High / Security     | Pending |
| TC-03 | Auth                      | Successful registration of a new account                                 | User does not already exist                                | 1. Open the register page.<br>2. Enter a new email, valid password, and matching confirm password.<br>3. Click Create Account.                  | The system creates the user; the user is redirected to the dashboard; the user can create a todo immediately.                                            | High / Major        | Pending |
| TC-04 | Todo Security             | User A cannot access or modify User B's todo                             | User A and User B both have accounts and are logged in     | 1. User B creates a new todo.<br>2. User A uses a separate session or API request.<br>3. Attempt to update or delete User B's todo.             | The system rejects the request with 403 or 404; User A cannot see User B's todo in their own list.                                                       | High / Critical     | Pending |
| TC-05 | Todo Logic                | Toggle from completed to incomplete persists                             | The todo is currently in the completed state               | 1. Open the completed todo.<br>2. Uncheck the checkbox.<br>3. Refresh the page or fetch the list again.                                         | The todo returns to the active state; completed=false is saved in the database and reflected in the UI after refresh.                                    | Medium / Major      | Pending |
| TC-06 | Todo Logic                | Partial update does not erase description                                | The todo has both a title and description                  | 1. Edit the title only and leave the description unchanged.<br>2. Save the change.<br>3. Refresh the list.                                      | The new title is applied; the original description remains intact; it is not overwritten or cleared.                                                     | Medium / Major      | Pending |
| TC-07 | Cross-User Data Isolation | User B cannot see User A's todo                                          | User A and User B each have separate accounts              | 1. User A signs in and creates a private todo.<br>2. User A logs out.<br>3. User B signs in from a separate session.<br>4. Check the todo list. | User B does not see User A's todo; the UI shows an empty-state list instead.                                                                             | High / Critical     | Pending |
| TC-08 | Cache                     | Cache is invalidated after todo changes                                  | The todo has already been cached for the current user      | 1. Create or update a todo.<br>2. Reload the page or call GET /todos again.<br>3. Compare the displayed data with the latest state.             | The UI shows the newest data and does not retain stale cache values after the mutation.                                                                  | Medium / Major      | Pending |
| TC-09 | Auth                      | Access token expiry is handled correctly                                 | User has a valid session but the token has expired         | 1. Attempt to access a protected route after the access token expires.<br>2. Observe the API response and UI behavior.                          | The app rejects the request with an authentication error and redirects or shows a session-expired state; the user is not allowed into protected content. | High / Critical     | Pending |
| TC-10 | Auth                      | Refresh token usage is restricted to valid sessions                      | User has a valid refresh token and an expired access token | 1. Try to refresh using a valid refresh token.<br>2. Repeat with a tampered or expired refresh token.                                           | Valid refresh token succeeds only when expected; invalid or tampered token is rejected and the session is not silently restored.                         | High / Critical     | Pending |
| TC-11 | Todo CRUD                 | Deleting a todo removes it immediately from the user’s list              | User has an existing todo                                  | 1. Create a todo.<br>2. Delete it from the UI or API.<br>3. Refresh the list.                                                                   | The todo is no longer visible; the total count and list contents update correctly.                                                                       | Medium / Major      | Pending |
| TC-12 | Todo CRUD                 | Empty or invalid todo title is rejected                                  | User is authenticated                                      | 1. Open the create-todo modal.<br>2. Submit the form without a title or with invalid data.<br>3. Observe validation behavior.                   | The form is rejected with a validation error and the todo is not created.                                                                                | Medium / Major      | Pending |
| TC-13 | UX / Session              | Logout clears session state and blocks access to protected routes        | User is authenticated                                      | 1. Sign in.<br>2. Click Logout.<br>3. Try to navigate back to a protected route or refresh the page.                                            | Session state is cleared; protected routes require re-authentication; no stale user context remains.                                                     | High / Major        | Pending |
| TC-14 | API Recovery              | Server error does not leave the UI in a stale or partially updated state | User is authenticated and a backend error is triggered     | 1. Attempt an invalid or rejected update.<br>2. Observe the UI and request result.                                                              | Error feedback is shown; the UI remains consistent; no stale optimistic state persists after failure.                                                    | Medium / Major      | Pending |

## 4. Expected Verification Notes

- These scenarios represent the manual test plan required by Tier 2 and are not results that were executed in this environment.
- When the tests are run in practice, record the following clearly:
  - Actual Result
  - Screenshots or API logs where relevant
  - Pass/fail status and the corresponding corrective action if a failure occurs

## 5. Defect Tracking & Known Limitations

- The current plan covers the core authentication, authorization, and todo flows but does not yet explicitly cover all edge conditions for malformed JWTs, session reuse after logout, or concurrent multi-tab updates.
- Outstanding scenarios not yet covered include:
  - expired access token used after session is already invalidated
  - refresh token replay or reuse after logout
  - tampered JWT payload causing authorization bypass or a clear rejection path
  - multi-tab updates where one tab modifies a todo while another tab remains stale
  - rate-limited or repeated failed login attempts and their effect on account lockout or UI messaging
  - pure API-only authorization checks for direct calls to protected todo endpoints without a valid frontend session
  - validation of stale cache after a logout/login transition when a different user signs in on the same browser
  - deletion or update operations against non-existent todo IDs to confirm 404 behavior
  - empty or invalid descriptions being rejected consistently when the business rule requires a title but not a description
- Some of these items should be treated as follow-up regression checks after the main authentication and todo ownership cases are validated.
- If a scenario is not feasible in the current environment, it should be documented with the reason and a retry plan in a full QA environment.
