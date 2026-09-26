from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    One users table for every role, with the role stored as a column.

    Extends Django's AbstractUser so we keep password hashing, is_active,
    the admin site etc. Defined before the first migration because swapping
    the user model later is painful in Django.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        PROVIDER = "provider", "Provider"
        CUSTOMER = "customer", "Customer"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    class Meta:
        constraints = [
            # choices= is only checked in Python; this enforces it in Postgres too.
            models.CheckConstraint(
                condition=models.Q(role__in=["admin", "provider", "customer"]),
                name="user_role_valid",
            ),
        ]

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_provider(self):
        return self.role == self.Role.PROVIDER

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def __str__(self):
        return f"{self.username} ({self.role})"
