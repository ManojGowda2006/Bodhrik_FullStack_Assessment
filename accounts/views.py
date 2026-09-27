from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import RegisterSerializer, RoleTokenObtainPairSerializer, UserSerializer


@extend_schema(auth=[])  # public: shown without the lock icon in the docs
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
