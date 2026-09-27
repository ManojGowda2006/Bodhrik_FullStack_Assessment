# Design Note

## Why this schema shape

Five tables: `users`, `slots`, `bookings`, `reviews`, `review_summaries`. Every role shares one `users` table with a `role` column, because authentication and authorisation need one place to look a person up. The cost is that role-specific fields (a provider's bio) would need a separate profile table.

Two deliberate normalisation tradeoffs:

- **`bookings.provider_id` is denormalised** from the slot. It never changes after creation, so it can't drift, and it makes the provider RBAC filter one indexed column instead of a join.
- **`slots.is_booked` is not stored.** Availability changes on every booking and cancellation, so a stored flag could drift. It is derived with an `EXISTS` subquery and cached in Redis.

Integrity lives in Postgres, not only in Python: a partial unique index allows one non-cancelled booking per slot (no double-booking even under concurrent requests, yet a cancelled slot can be rebooked), a one-to-one gives one review per booking, and check constraints guard role, status, rating and slot times.

## RBAC for a fourth role or nested organisations

Access control has two layers. `RBACMiddleware` authenticates the JWT and checks a `(route, method) → roles` table (403). Row scoping lives in one function, `Booking.objects.visible_to(user)` (404, so other users' bookings aren't revealed to exist).

A fourth role such as `support` is mostly data: add it to the role choices, `ROLE_POLICY`, `Booking.TRANSITIONS` and one branch in `visible_to()`. Beyond a few roles I would map roles to permissions (`bookings.read_all`) rather than to routes directly.

Nested organisations change the row question from "is this mine?" to "does this belong to my organisation or one below it?". That needs an `organisations` table with a parent link, an `organisation_id` on users and slots, and `visible_to()` filtering by the user's subtree (a recursive CTE or a materialised path). The middleware barely changes; the querysets carry the weight, which is why scoping sits in one place.

## What's missing for production

- **Migrations** run when the web container starts. With several replicas they would race, so they belong in a separate release step, using expand-then-contract changes so old and new code both work during a deploy.
- **Secrets** come from `.env`. Production needs a secrets manager, a generated `DJANGO_SECRET_KEY`, rotation, and `DEBUG=false`.
- **Auth**: no logout or token revocation (simplejwt's blacklist would add it), and no rate limiting on login.
- **Jobs**: no automatic retries, a summary stays `running` if the worker dies mid-job, and Redis has no persistence configured, so queued jobs can be lost. It needs RQ retries, a cleanup job for stuck rows, and Redis AOF.
- **Operations**: no HTTPS or security-header configuration, structured logging, metrics or error tracking.
- **Domain**: slots are only unique by start time; preventing overlapping slots needs a Postgres exclusion constraint.
