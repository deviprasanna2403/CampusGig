"""
Phase 9 data migration (one-time backfill).

The pre-Phase-9 workflow could mark a BusinessVerification as VERIFIED
without ever setting the business user's is_verified flag — the Phase 5
publish gate (IsVerified) therefore stayed shut for legitimately verified
businesses. This migration closes that historical gap: every business user
whose verification is VERIFIED gets is_verified=True. Idempotent.
"""

from django.db import migrations


def backfill_verified_businesses(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    BusinessVerification = apps.get_model("safety", "BusinessVerification")

    # Historical models (apps.get_model) carry fields only — no inner
    # Status class — so the status value must be the literal string.
    verified_business_user_ids = BusinessVerification.objects.filter(
        status="VERIFIED"
    ).values_list("business__user_id", flat=True)

    User.objects.filter(id__in=verified_business_user_ids, is_verified=False).update(
        is_verified=True
    )


def un_backfill(apps, schema_editor):
    # Reversing would require knowing which flags were backfilled vs
    # legitimately set; do nothing (safe no-op) on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("safety", "0002_alter_businessverification_status"),
        # Safety 0001 already depends on accounts' latest, but be explicit:
        # the backfill writes accounts_user rows.
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_verified_businesses, un_backfill),
    ]
