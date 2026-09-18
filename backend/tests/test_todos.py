"""Todo tests."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    # Create a todo first
    await client.post(
        "/api/v1/todos",
        json={"title": "List Todo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get todos
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_user_cannot_access_other_users_todo(client: AsyncClient):
    """Users should not read, update, or delete another user's todo."""
    user_a_token = await get_auth_token(client, "owner-a@example.com")
    user_b_token = await get_auth_token(client, "owner-b@example.com")

    todo_response = await client.post(
        "/api/v1/todos",
        json={"title": "Private Todo"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    todo_id = todo_response.json()["id"]

    read_response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert read_response.status_code == 403

    update_response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Attempted Update"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert update_response.status_code == 403

    delete_response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert delete_response.status_code == 403


@pytest.mark.asyncio
async def test_partial_updates_preserve_omitted_fields_and_false_completed(client: AsyncClient):
    """Partial updates must preserve existing fields and apply false boolean values."""
    token = await get_auth_token(client, "partial@example.com")

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Initial Todo", "description": "Keep me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Keep me"
    assert data["completed"] is False

    second_response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Final Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["description"] == "Keep me"
    assert second_data["title"] == "Final Title"


@pytest.mark.asyncio
async def test_todo_cache_is_user_scoped_and_invalidated(client: AsyncClient):
    """List cache keys should be user-scoped and invalidated on mutation."""
    from unittest.mock import AsyncMock, MagicMock

    from app.api.deps import get_redis
    from app.main import app

    original_override = app.dependency_overrides.get(get_redis)
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.delete_pattern = AsyncMock()
    mock_redis.scan_iter = MagicMock(return_value=[])
    app.dependency_overrides[get_redis] = lambda: mock_redis

    try:
        token = await get_auth_token(client, "cache@example.com")

        create_response = await client.post(
            "/api/v1/todos",
            json={"title": "Cache Todo"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_response.status_code == 201
        mock_redis.delete_pattern.assert_called_with(
            f"todos:list:{create_response.json()['user_id']}:*"
        )

        list_response = await client.get(
            "/api/v1/todos",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        mock_redis.get.assert_any_call(
            f"todos:list:{create_response.json()['user_id']}:1:20"
        )
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_redis, None)
        else:
            app.dependency_overrides[get_redis] = original_override


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Update Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Update it
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Single Todo", "description": "Get me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Get it
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"
