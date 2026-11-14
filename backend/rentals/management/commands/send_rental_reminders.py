import time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.notifications import notify
from rentals.models import Rental


class Command(BaseCommand):
    help = "Send email and SMS reminder notifications for rentals ending soon."

    def add_arguments(self, parser):
        default_hours = getattr(settings, "RENTAL_REMINDER_HOURS", 3)
        parser.add_argument(
            "--hours",
            type=int,
            default=default_hours,
            help=f"Hours ahead to check for ending rentals (default: {default_hours}).",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Run continuously in a periodic loop.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Interval in seconds between iterations when running with --loop (default: 60).",
        )

    def process_reminders(self, hours):
        """
        Query handed_over rentals ending within now..now+hours without a reminder sent.
        Dispatches notification via dual channels (email and SMS), and marks reminder_sent_at
        if at least one channel was successfully sent.
        """
        rentals = (
            Rental.objects.ending_soon(hours)
            .select_related("renter", "item")
            .order_by("end_at")
        )

        sent_count = 0
        tehran_tz = ZoneInfo("Asia/Tehran")

        for rental in rentals:
            end_at_tehran = rental.end_at.astimezone(tehran_tz).strftime("%Y/%m/%d ساعت %H:%M")
            title = rental.item.title if hasattr(rental, "item") and rental.item else "کالای امانتی"

            context = {
                "title": title,
                "end_at": end_at_tehran,
            }

            logs = notify(
                user=rental.renter,
                event="rental_ending_soon",
                context=context,
                item=rental.item,
                rental=rental,
            )

            # Check if at least one channel was sent
            was_sent = any(getattr(log, "status", None) == "sent" for log in logs)
            if was_sent:
                rental.reminder_sent_at = timezone.now()
                rental.save(update_fields=["reminder_sent_at"])
                sent_count += 1
                self.stdout.write(
                    f"Reminder sent for Rental #{rental.pk} ({title}) to {rental.renter.username}."
                )

        return sent_count

    def handle(self, *args, **options):
        hours = options["hours"]
        loop = options["loop"]
        interval = options["interval"]

        if not loop:
            sent_count = self.process_reminders(hours)
            self.stdout.write(
                self.style.SUCCESS(f"Sent {sent_count} reminder(s).")
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Starting reminder service loop (hours={hours}, interval={interval}s). "
                "Press Ctrl+C to terminate."
            )
        )

        try:
            while True:
                sent_count = self.process_reminders(hours)
                now_str = timezone.now().astimezone(ZoneInfo("Asia/Tehran")).strftime("%H:%M:%S")
                self.stdout.write(
                    f"[{now_str}] Iteration finished: {sent_count} reminder(s) sent. "
                    f"Sleeping for {interval}s..."
                )
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Reminder service loop stopped."))
