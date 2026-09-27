from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # Self-registration is limited to provider/customer. Admins are created
    # by an existing admin (createsuperuser / Django admin), never via the API.
    role = serializers.ChoiceField(
        choices=[User.Role.PROVIDER, User.Role.CUSTOMER],
        default=User.Role.CUSTOMER,
    )

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "role")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        # create_user hashes the password; never store it as plain text.
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role")


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the role to the JWT so clients can read it without an extra call.

    The API never trusts this claim for authorization: simplejwt loads the
    user from the DB on every request, so a role change applies immediately.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token
