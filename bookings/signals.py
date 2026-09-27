"""
Invalidate the slot list cache whenever slots or bookings change.

Signals rather than calls in the views, so writes from anywhere (API,
Django admin, shell, worker) are covered. A booking change matters too:
creating or cancelling one flips the slot's is_available.

on_commit: invalidate only once the change is committed. Invalidating
earlier would let a concurrent reader re-cache the old data in between.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from bookings.cache import invalidate_slot_lists
from bookings.models import Booking, Slot


@receiver([post_save, post_delete], sender=Slot)
@receiver([post_save, post_delete], sender=Booking)
def slot_data_changed(sender, **kwargs):
    transaction.on_commit(invalidate_slot_lists)
