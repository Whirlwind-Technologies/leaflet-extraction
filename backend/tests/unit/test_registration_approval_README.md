# Registration Approval Tests

## Overview

This test suite verifies the complete registration approval workflow including:
- Personal and business user registration (pending approval)
- Login blocking for inactive users
- Admin approve/reject functionality
- Edge cases and security checks

## Test File

`test_registration_approval.py` - 18 comprehensive tests covering all aspects of the registration approval system.

## Test Coverage

### Personal Registration (3 tests)
1. ✓ Personal registration creates inactive user (`is_active=False`)
2. ✓ Personal registration returns pending approval message
3. ✓ Personal registration creates personal organization automatically

### Business Registration (2 tests)
4. ✓ Business registration creates inactive user
5. ✓ Business registration creates organization with `PENDING_APPROVAL` status

### Login Blocking (3 tests)
6. ✓ Inactive personal user cannot log in (returns 403 with "pending approval" message)
7. ✓ Inactive business user cannot log in (returns 403 with "business registration pending")
8. ✓ Active user can log in normally (returns 200 with tokens)

### Admin Approve (4 tests)
9. ✓ Superuser can approve pending user (sets `is_active=True`, `is_verified=True`)
10. ✓ Cannot approve already-active user (returns 400 "already approved")
11. ✓ Cannot approve yourself (returns 400 "Cannot approve your own account")
12. ✓ Non-superuser cannot access approve endpoint (returns 403)

### Admin Reject (4 tests)
13. ✓ Superuser can reject pending user (keeps `is_active=False`, sets org to `SUSPENDED`)
14. ✓ Reject with reason (reason is stored on organization)
15. ✓ Cannot reject a superuser (returns 400 "Cannot reject a superuser")
16. ✓ Non-superuser cannot access reject endpoint (returns 403)

### Edge Cases (2 tests)
17. ✓ Rejected user still cannot log in (returns 403 with "suspended" status)
18. ✓ Approved user can log in successfully (returns 200 with tokens)

## Running the Tests

### Prerequisites

1. **Database**: PostgreSQL test database must be running
   ```bash
   # Create test database
   createdb test_leaflet_db
   ```

2. **Environment**: Test environment variables are set in `conftest.py`:
   - `POSTGRES_HOST=localhost`
   - `POSTGRES_PORT=5432`
   - `POSTGRES_USER=postgres`
   - `POSTGRES_PASSWORD=postgres`
   - `POSTGRES_DB=leaflet_db`

   Test database is automatically prefixed with `test_` → `test_leaflet_db`

### Run All Tests

```bash
cd backend
python -m pytest tests/unit/test_registration_approval.py -v
```

### Run Specific Test Class

```bash
# Test only personal registration
python -m pytest tests/unit/test_registration_approval.py::TestPersonalRegistration -v

# Test only login blocking
python -m pytest tests/unit/test_registration_approval.py::TestLoginBlocking -v

# Test only admin approve
python -m pytest tests/unit/test_registration_approval.py::TestAdminApprove -v
```

### Run Single Test

```bash
python -m pytest tests/unit/test_registration_approval.py::TestPersonalRegistration::test_personal_registration_creates_inactive_user -v
```

### With Coverage

```bash
python -m pytest tests/unit/test_registration_approval.py --cov=app.api.v1.auth --cov=app.api.v1.admin.users --cov-report=term-missing
```

## Mocking Strategy

### Email Service
All tests mock the email service to prevent actual email sending:
```python
with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
    # Test registration endpoint
```

### Notification Service
Notifications are mocked via the `_send_registration_notifications` helper, which is patched in tests.

### Database
Tests use the pytest-async fixtures from `conftest.py`:
- `db_session`: Async database session with automatic rollback
- `test_user`: Pre-created active user
- `test_superuser`: Pre-created superuser
- `client`: Async HTTP test client

## Test Patterns

### Creating Inactive Users
```python
from app.utils.security import hash_password

user = User(
    id=uuid4(),
    email="inactive@example.com",
    hashed_password=hash_password("TestPass123"),
    full_name="Inactive User",
    is_active=False,  # Key: pending approval
    is_verified=False,
)
```

### Testing Login Blocking
```python
response = await client.post(
    "/api/v1/auth/login",
    json={"email": "inactive@example.com", "password": "TestPass123"},
)

assert response.status_code == 403
data = response.json()
assert data["detail"]["status"] == "pending_approval"
```

### Testing Admin Endpoints
```python
from app.utils.security import create_access_token

token = create_access_token(data={"sub": str(test_superuser.id)})

response = await client.post(
    f"/api/v1/admin/users/{user_id}/approve",
    headers={"Authorization": f"Bearer {token}"},
)

assert response.status_code == 200
```

## Known Issues

### Database Connection
If tests fail with `asyncpg.exceptions.InvalidPasswordError`, verify:
1. PostgreSQL is running: `pg_isready`
2. Test database exists: `psql -l | grep test_leaflet_db`
3. Credentials match `conftest.py` settings

### Conftest Environment
Tests depend on environment variables being set correctly in `conftest.py` before importing `app.config`. The CORS_ORIGINS must be a valid JSON array:
```python
os.environ["CORS_ORIGINS"] = '["http://localhost:3000", "http://localhost:8000"]'
```

## Maintenance Notes

### Adding New Tests
When adding new tests for registration approval:
1. Follow the existing class structure (`TestPersonalRegistration`, `TestAdminApprove`, etc.)
2. Mock the email service to prevent actual emails
3. Use the async patterns from existing tests
4. Verify user state in database after operations
5. Check both HTTP response and database state

### Updating Fixtures
If registration flow changes:
1. Update `test_user` and `test_superuser` fixtures in `conftest.py` if needed
2. Update organization creation patterns if organization model changes
3. Check that organization status transitions are correct

### Security Considerations
These tests verify critical security boundaries:
- ✅ Inactive users cannot log in
- ✅ Regular users cannot approve/reject
- ✅ Users cannot approve themselves
- ✅ Superusers cannot be rejected
- ✅ Rejected users remain locked out

Do not modify these security checks without careful review.
