"""
Role checks used by every view.

These answer "may this role call this endpoint at all?" (403 if not).
Which rows a user may see is a separate question, answered by querysets
such as Booking.objects.visible_to(user) (404 if not).
"""

from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_role


class IsProvider(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_provider


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_customer
