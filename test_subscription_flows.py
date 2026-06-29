import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from dateutil.relativedelta import relativedelta

import services.payments as payments


def dt(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


class FakeRepo:
    def __init__(self):
        self.subscriptions = {}
        self.subscription_payments = []

    def seed_subscription(self, telegram_id, **fields):
        row = {
            "telegram_id": telegram_id,
            "status": "pending_confirmation",
            "payment_method_id": None,
            "trial_starts_at": None,
            "trial_ends_at": None,
            "current_period_ends_at": None,
            "next_charge_at": None,
            "last_payment_id": None,
            "last_error": None,
            "canceled_at": None,
            "trial_reminded_at": None,
            "created_at": payments.iso_dt(dt(2026, 1, 1)),
            "updated_at": payments.iso_dt(dt(2026, 1, 1)),
        }
        row.update(fields)
        self.subscriptions[telegram_id] = row
        return row

    def get_subscription(self, telegram_id):
        row = self.subscriptions.get(telegram_id)
        return copy.deepcopy(row) if row else None

    def upsert_subscription(self, row):
        telegram_id = row["telegram_id"]
        existing = self.subscriptions.get(telegram_id, {})
        merged = {**existing, **copy.deepcopy(row)}
        self.subscriptions[telegram_id] = merged
        return merged

    def update_subscription(self, telegram_id, fields):
        existing = self.subscriptions.get(telegram_id)
        if not existing:
            raise AssertionError(f"Subscription {telegram_id} does not exist in fake repo")
        existing.update(copy.deepcopy(fields))
        self.subscriptions[telegram_id] = existing
        return existing

    def get_due_subscriptions(self, limit=50):
        current_time = payments.now_utc()
        due = []

        for row in self.subscriptions.values():
            if row.get("status") not in ("trialing", "active"):
                continue

            next_charge_at = payments.parse_dt(row.get("next_charge_at"))
            if next_charge_at and next_charge_at <= current_time:
                due.append(copy.deepcopy(row))

        due.sort(key=lambda item: item["telegram_id"])
        return due[:limit]

    def get_trial_reminder_subscriptions(self, limit=50):
        current_time = payments.now_utc()
        reminder_window_ends_at = current_time + payments.TRIAL_END_REMINDER_LEAD_TIME
        due = []

        for row in self.subscriptions.values():
            if row.get("status") != "trialing":
                continue

            if row.get("payment_method_id"):
                continue

            if row.get("trial_reminded_at"):
                continue

            trial_ends_at = payments.parse_dt(row.get("trial_ends_at"))
            if trial_ends_at and current_time < trial_ends_at <= reminder_window_ends_at:
                due.append(copy.deepcopy(row))

        due.sort(key=lambda item: item["telegram_id"])
        return due[:limit]

    def save_subscription_payment(self, payment, status):
        self.subscription_payments.append(
            {
                "payment_id": payment.get("id"),
                "status": status,
                "telegram_id": int((payment.get("metadata") or {}).get("telegram_id", 0) or 0),
            }
        )


class SubscriptionFlowsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.fake_bot = AsyncMock()
        self.fixed_now = dt(2026, 6, 1, 7, 13)
        self.patches = [
            patch.object(payments, "get_subscription", side_effect=self.repo.get_subscription),
            patch.object(payments, "upsert_subscription", side_effect=self.repo.upsert_subscription),
            patch.object(payments, "update_subscription", side_effect=self.repo.update_subscription),
            patch.object(payments, "get_due_subscriptions", side_effect=self.repo.get_due_subscriptions),
            patch.object(
                payments,
                "get_trial_reminder_subscriptions",
                side_effect=self.repo.get_trial_reminder_subscriptions,
            ),
            patch.object(payments, "save_subscription_payment", side_effect=self.repo.save_subscription_payment),
            patch.object(payments, "has_saved_subscription_payment", return_value=False),
            patch.object(payments, "bot", self.fake_bot),
            patch.object(payments, "main_keyboard", return_value=None),
            patch.object(payments, "now_utc", side_effect=lambda: self.fixed_now),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    async def test_first_time_trial_activation_opens_access_without_card(self):
        telegram_id = 101
        payments.activate_free_trial(telegram_id)

        subscription = self.repo.get_subscription(telegram_id)
        trial_end = self.fixed_now + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)

        self.assertEqual(subscription["status"], "trialing")
        self.assertIsNone(subscription["payment_method_id"])
        self.assertEqual(subscription["trial_starts_at"], payments.iso_dt(self.fixed_now))
        self.assertEqual(subscription["trial_ends_at"], payments.iso_dt(trial_end))
        self.assertEqual(subscription["current_period_ends_at"], payments.iso_dt(trial_end))
        self.assertIsNone(subscription["next_charge_at"])
        self.assertTrue(payments.is_subscription_active(subscription))
        self.assertFalse(payments.is_subscription_auto_renewing(subscription))

    async def test_trial_end_successful_charge_keeps_access_and_renews(self):
        telegram_id = 102
        trial_start = dt(2026, 6, 1, 7, 13)
        trial_end = trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.fixed_now = trial_end
        self.repo.seed_subscription(
            telegram_id,
            status="trialing",
            payment_method_id="pm_102",
            trial_starts_at=payments.iso_dt(trial_start),
            trial_ends_at=payments.iso_dt(trial_end),
            current_period_ends_at=payments.iso_dt(trial_end),
            next_charge_at=payments.iso_dt(trial_end),
        )

        with patch.object(
            payments,
            "create_recurring_payment",
            return_value={
                "id": "pay_trial_success",
                "status": "succeeded",
                "metadata": {"telegram_id": str(telegram_id)},
                "amount": {"value": "1990.00", "currency": "RUB"},
            },
        ):
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)
        renewed_until = trial_end + relativedelta(months=1)

        self.assertEqual(result["due"], 1)
        self.assertEqual(result["charged"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["current_period_ends_at"], payments.iso_dt(renewed_until))
        self.assertEqual(subscription["next_charge_at"], payments.iso_dt(renewed_until))
        self.assertEqual(subscription["last_payment_id"], "pay_trial_success")
        self.assertTrue(payments.is_subscription_active(subscription))

    async def test_trial_end_failed_charge_closes_access(self):
        telegram_id = 103
        trial_start = dt(2026, 6, 1, 7, 13)
        trial_end = trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.fixed_now = trial_end
        self.repo.seed_subscription(
            telegram_id,
            status="trialing",
            payment_method_id="pm_103",
            trial_starts_at=payments.iso_dt(trial_start),
            trial_ends_at=payments.iso_dt(trial_end),
            current_period_ends_at=payments.iso_dt(trial_end),
            next_charge_at=payments.iso_dt(trial_end),
        )

        with patch.object(payments, "create_recurring_payment", side_effect=RuntimeError("card_declined")):
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(result["due"], 1)
        self.assertEqual(result["charged"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(subscription["status"], "past_due")
        self.assertEqual(subscription["last_error"], "card_declined")
        self.assertFalse(payments.is_subscription_active(subscription))

    async def test_monthly_charge_success_extends_from_current_period_end(self):
        telegram_id = 104
        current_period_end = dt(2026, 7, 1, 9, 0)
        self.fixed_now = current_period_end + timedelta(days=3)
        self.repo.seed_subscription(
            telegram_id,
            status="active",
            payment_method_id="pm_104",
            current_period_ends_at=payments.iso_dt(current_period_end),
            next_charge_at=payments.iso_dt(current_period_end),
        )

        with patch.object(
            payments,
            "create_recurring_payment",
            return_value={
                "id": "pay_month_success",
                "status": "succeeded",
                "metadata": {"telegram_id": str(telegram_id)},
                "amount": {"value": "1990.00", "currency": "RUB"},
            },
        ):
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)
        renewed_until = current_period_end + relativedelta(months=1)

        self.assertEqual(result["charged"], 1)
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["current_period_ends_at"], payments.iso_dt(renewed_until))
        self.assertEqual(subscription["next_charge_at"], payments.iso_dt(renewed_until))
        self.assertTrue(payments.is_subscription_active(subscription))

    async def test_monthly_charge_failure_disables_access(self):
        telegram_id = 105
        current_period_end = dt(2026, 7, 1, 9, 0)
        self.fixed_now = current_period_end
        self.repo.seed_subscription(
            telegram_id,
            status="active",
            payment_method_id="pm_105",
            current_period_ends_at=payments.iso_dt(current_period_end),
            next_charge_at=payments.iso_dt(current_period_end),
        )

        with patch.object(
            payments,
            "create_recurring_payment",
            return_value={
                "id": "pay_month_failed",
                "status": "canceled",
                "metadata": {"telegram_id": str(telegram_id)},
                "amount": {"value": "1990.00", "currency": "RUB"},
                "cancellation_details": {"reason": "insufficient_funds"},
            },
        ):
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(result["charged"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(subscription["status"], "past_due")
        self.assertEqual(subscription["last_error"], "insufficient_funds")
        self.assertFalse(payments.is_subscription_active(subscription))

    async def test_monthly_charge_pending_is_saved_and_rescheduled(self):
        telegram_id = 109
        current_period_end = dt(2026, 7, 1, 9, 0)
        self.fixed_now = current_period_end
        self.repo.seed_subscription(
            telegram_id,
            status="active",
            payment_method_id="pm_109",
            current_period_ends_at=payments.iso_dt(current_period_end),
            next_charge_at=payments.iso_dt(current_period_end),
        )

        with patch.object(
            payments,
            "create_recurring_payment",
            return_value={
                "id": "pay_month_pending",
                "status": "pending",
                "metadata": {"telegram_id": str(telegram_id)},
                "amount": {"value": "1990.00", "currency": "RUB"},
            },
        ):
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)
        expected_retry_at = self.fixed_now + timedelta(
            minutes=max(payments.SUBSCRIPTION_ACCESS_GRACE_MINUTES, 5)
        )

        self.assertEqual(result["due"], 1)
        self.assertEqual(result["charged"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["last_payment_id"], "pay_month_pending")
        self.assertEqual(subscription["last_error"], "Recurring payment pending: pending")
        self.assertEqual(subscription["next_charge_at"], payments.iso_dt(expected_retry_at))
        self.assertEqual(
            self.repo.subscription_payments,
            [
                {
                    "payment_id": "pay_month_pending",
                    "status": "pending",
                    "telegram_id": telegram_id,
                }
            ],
        )

    async def test_free_trial_without_card_is_not_charged_when_it_ends(self):
        telegram_id = 112
        trial_start = dt(2026, 6, 1, 7, 13)
        trial_end = trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.fixed_now = trial_end + timedelta(minutes=1)
        self.repo.seed_subscription(
            telegram_id,
            status="trialing",
            payment_method_id=None,
            trial_starts_at=payments.iso_dt(trial_start),
            trial_ends_at=payments.iso_dt(trial_end),
            current_period_ends_at=payments.iso_dt(trial_end),
            next_charge_at=None,
        )

        with patch.object(payments, "create_recurring_payment") as create_payment:
            result = await payments.charge_due_subscriptions()

        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(result["due"], 0)
        create_payment.assert_not_called()
        self.assertEqual(subscription["status"], "trialing")
        self.assertFalse(payments.is_subscription_active(subscription))

    async def test_trial_expiring_reminder_is_sent_once_one_day_before_end(self):
        telegram_id = 113
        trial_start = dt(2026, 6, 1, 7, 13)
        trial_end = trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.fixed_now = trial_end - timedelta(hours=23)
        self.repo.seed_subscription(
            telegram_id,
            status="trialing",
            payment_method_id=None,
            trial_starts_at=payments.iso_dt(trial_start),
            trial_ends_at=payments.iso_dt(trial_end),
            current_period_ends_at=payments.iso_dt(trial_end),
            next_charge_at=None,
        )

        result = await payments.send_trial_expiring_reminders()
        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(result, {"due": 1, "sent": 1, "failed": 0})
        self.assertEqual(subscription["trial_reminded_at"], payments.iso_dt(self.fixed_now))
        self.fake_bot.send_message.assert_awaited_once()

        second_result = await payments.send_trial_expiring_reminders()

        self.assertEqual(second_result, {"due": 0, "sent": 0, "failed": 0})
        self.fake_bot.send_message.assert_awaited_once()

    async def test_cancel_subscription_keeps_access_until_period_end(self):
        telegram_id = 106
        period_end = dt(2026, 7, 10, 12, 0)
        self.fixed_now = dt(2026, 7, 1, 12, 0)
        self.repo.seed_subscription(
            telegram_id,
            status="active",
            payment_method_id="pm_106",
            current_period_ends_at=payments.iso_dt(period_end),
            next_charge_at=payments.iso_dt(period_end),
        )

        payments.cancel_subscription(telegram_id)
        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(subscription["status"], "canceled")
        self.assertIsNone(subscription["next_charge_at"])
        self.assertTrue(payments.is_subscription_active(subscription))
        self.assertFalse(payments.is_subscription_auto_renewing(subscription))

        self.fixed_now = period_end + timedelta(minutes=1)
        self.assertFalse(payments.is_subscription_active(self.repo.get_subscription(telegram_id)))

    async def test_replace_payment_method_keeps_active_subscription_dates(self):
        telegram_id = 110
        period_end = dt(2026, 7, 10, 12, 0)
        self.fixed_now = dt(2026, 7, 1, 12, 0)
        self.repo.seed_subscription(
            telegram_id,
            status="active",
            payment_method_id="pm_old",
            current_period_ends_at=payments.iso_dt(period_end),
            next_charge_at=payments.iso_dt(period_end),
            last_error="old_card_error",
        )

        await payments.handle_payment_method_active(
            {
                "id": "pm_new",
                "status": "active",
                "saved": True,
                "metadata": {
                    "telegram_id": str(telegram_id),
                    "action": payments.SUBSCRIPTION_ACTION_REPLACE_PAYMENT_METHOD,
                },
            }
        )

        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["payment_method_id"], "pm_new")
        self.assertEqual(subscription["current_period_ends_at"], payments.iso_dt(period_end))
        self.assertEqual(subscription["next_charge_at"], payments.iso_dt(period_end))
        self.assertIsNone(subscription["last_error"])
        self.assertTrue(payments.is_subscription_active(subscription))
        self.fake_bot.send_message.assert_awaited()

    async def test_replace_payment_method_for_past_due_charges_immediately(self):
        telegram_id = 111
        old_period_end = dt(2026, 6, 1, 12, 0)
        self.fixed_now = dt(2026, 6, 5, 12, 0)
        self.repo.seed_subscription(
            telegram_id,
            status="past_due",
            payment_method_id="pm_old",
            current_period_ends_at=payments.iso_dt(old_period_end),
            next_charge_at=None,
            last_error="insufficient_funds",
        )

        with patch.object(
            payments,
            "create_recurring_payment",
            return_value={
                "id": "pay_replacement_success",
                "status": "succeeded",
                "metadata": {"telegram_id": str(telegram_id)},
                "amount": {"value": "1990.00", "currency": "RUB"},
            },
        ):
            await payments.handle_payment_method_active(
                {
                    "id": "pm_new",
                    "status": "active",
                    "saved": True,
                    "metadata": {
                        "telegram_id": str(telegram_id),
                        "action": payments.SUBSCRIPTION_ACTION_REPLACE_PAYMENT_METHOD,
                    },
                }
            )

        subscription = self.repo.get_subscription(telegram_id)
        renewed_until = self.fixed_now + relativedelta(months=1)

        self.assertEqual(subscription["status"], "active")
        self.assertEqual(subscription["payment_method_id"], "pm_new")
        self.assertEqual(subscription["current_period_ends_at"], payments.iso_dt(renewed_until))
        self.assertEqual(subscription["next_charge_at"], payments.iso_dt(renewed_until))
        self.assertEqual(subscription["last_payment_id"], "pay_replacement_success")
        self.assertIsNone(subscription["last_error"])
        self.assertTrue(payments.is_subscription_active(subscription))

    async def test_used_trial_cannot_be_activated_again(self):
        telegram_id = 107
        old_trial_start = dt(2026, 5, 1, 10, 0)
        old_trial_end = old_trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.repo.seed_subscription(
            telegram_id,
            status="canceled",
            payment_method_id="pm_old",
            trial_starts_at=payments.iso_dt(old_trial_start),
            trial_ends_at=payments.iso_dt(old_trial_end),
            current_period_ends_at=payments.iso_dt(old_trial_end),
        )

        payments.activate_subscription(telegram_id, "pm_new")
        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(subscription["status"], "canceled")
        self.assertEqual(subscription["payment_method_id"], "pm_old")
        self.assertTrue(payments.has_used_trial(subscription))
        self.assertIn("Бесплатный период уже был использован", payments.start_offer_text(subscription))

    async def test_return_after_used_trial_does_not_start_second_free_period(self):
        telegram_id = 108
        old_trial_start = dt(2026, 5, 1, 10, 0)
        old_trial_end = old_trial_start + timedelta(days=payments.SUBSCRIPTION_TRIAL_DAYS)
        self.repo.seed_subscription(
            telegram_id,
            status="pending_confirmation",
            payment_method_id="pm_108",
            trial_starts_at=payments.iso_dt(old_trial_start),
            trial_ends_at=payments.iso_dt(old_trial_end),
            current_period_ends_at=payments.iso_dt(old_trial_end),
        )

        with patch.object(
            payments,
            "get_payment_method",
            return_value={
                "id": "pm_108",
                "status": "active",
                "saved": True,
                "metadata": {"telegram_id": str(telegram_id)},
            },
        ):
            result = payments.activate_subscription_from_return(
                telegram_id=telegram_id,
                payment_method_id="pm_108",
            )

        subscription = self.repo.get_subscription(telegram_id)

        self.assertEqual(result, "payment_pending")
        self.assertEqual(subscription["status"], "pending_confirmation")
        self.assertTrue(payments.has_used_trial(subscription))


if __name__ == "__main__":
    unittest.main()
