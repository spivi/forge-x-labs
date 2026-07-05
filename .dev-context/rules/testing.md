# Testing Rules

## Framework & Config

- pytest + pytest-asyncio in **auto mode** (`asyncio_mode = "auto"` in pyproject.toml)
- httpx `AsyncClient` for integration tests against the FastAPI app
- All test functions are `async def` — no sync test functions for async code
- Test files mirror source structure: `tests/api/v1/test_users.py` → `app/api/v1/users.py`

## Fixtures (conftest.py)

```python
@pytest.fixture
async def session():
    """Isolated async session with transaction rollback."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        async_session = AsyncSession(bind=conn)
        yield async_session
        await trans.rollback()

@pytest.fixture
async def client(session):
    """Test client with dependency overrides."""
    app.dependency_overrides[get_session] = lambda: session
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

## Mocking Strategy

- Use `app.dependency_overrides` to swap dependencies — not monkeypatch on imports
- Mock at the boundary: replace repositories in service tests, replace services in API tests
- External services (email, S3, webhooks): always mocked, never called in tests
- Use `unittest.mock.AsyncMock` for async callables

## factory-boy Fixtures

- One factory per ORM model in `tests/factories/`
- Factories use `SQLAlchemyModelFactory` with async session support
- Use `factory.LazyAttribute` and `factory.Sequence` for unique values
- Never hardcode test data inline — use factories

```python
class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    name = factory.Faker("name")
```

## Test Structure

- Arrange / Act / Assert — one blank line between each section
- One assertion per test function (or closely related group)
- Test names: `test_<action>_<condition>_<expected>` e.g., `test_create_user_duplicate_email_returns_409`
- No test function longer than 20 lines. Extract helpers if needed

## Edge Cases & Scenarios

- **Mandrake Testing**: Every new functionality must include unit tests for:
  - Happy path (standard usage).
  - Multiple error paths (invalid input, resource not found, etc.).
  - Edge cases (empty strings, zero values, boundary conditions, long inputs).
- Use `pytest.mark.parametrize` to test high-variance scenarios efficiently.

## E2E Testing (GUI)

- **Mandatory for GUI**: If a feature involves a user interface (Web, Desktop, etc.), E2E tests must be implemented.
- Use Playwright (for Web) or another appropriate framework to ensure the full user flow works as expected.
- E2E tests should cover critical paths (e.g., login, create resource, delete resource).

## Coverage & CI

- Minimum 80% line coverage enforced in CI
- Coverage excludes: `conftest.py`, `factories/`, `migrations/`
- Every public API endpoint has at least one happy-path and one error-path test
