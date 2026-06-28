# 0005: Custom User Model

Status: Accepted

Decision:

Introduce a custom user model now, before any domain models exist:

```python
accounts.User extends django.contrib.auth.models.AbstractUser
AUTH_USER_MODEL = "accounts.User"
```

Rationale:

- Future domain models will reference staff users (e.g. who created or worked a
  repair order). Swapping `AUTH_USER_MODEL` after those references exist is
  expensive and migration-heavy.
- Doing it now, while there is no real data, is cheap and avoids later pain.
- `AbstractUser` keeps Django's standard username/password authentication,
  admin integration, groups, and permissions intact.

Scope for now:

- Standard Django username/password authentication only.
- No extra fields on the user model yet.
- Baseline staff role groups created via data migration (names only).

Explicitly out of scope (later, if needed):

- Password reset / email flows
- Two-factor authentication
- SSO
- Third-party auth packages
