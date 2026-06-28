from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model for Unicos staff.

    Introduced now, before domain models exist, because switching the
    ``AUTH_USER_MODEL`` after other models reference it is expensive. No extra
    fields are added yet; future domain models will reference staff users via
    this model.
    """

    pass
