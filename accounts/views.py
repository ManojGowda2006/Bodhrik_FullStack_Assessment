from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import RegisterSerializer, RoleTokenObtainPairSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
