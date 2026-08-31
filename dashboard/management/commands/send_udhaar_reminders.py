"""
Sends a WhatsApp reminder to every customer whose udhaar (credit) balance
is above zero and hasn't been reminded in the last 7 days.

Run manually:
    python manage.py send_udhaar_reminders

Or schedule it with cron (Linux/Mac) to run daily, e.g.:
    0 10 * * * cd /path/to/smart_dukaan && /path/to/venv/bin/python manage.py send_udhaar_reminders

On Windows, use Task Scheduler to run the same command daily.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from udhaar.models import Customer, UdhaarTransaction
from billing.utils import send_whatsapp_message, build_udhaar_reminder_message


class Command(BaseCommand):
    help = "Send WhatsApp udhaar reminders to customers with pending dues"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=7)
        sent_count = 0
        skipped_count = 0

        for customer in Customer.objects.all():
            if customer.total_due <= 0:
                continue

            last_reminder = customer.transactions.filter(
                reminder_sent_at__isnull=False
            ).order_by("-reminder_sent_at").first()

            if last_reminder and last_reminder.reminder_sent_at and last_reminder.reminder_sent_at > cutoff:
                skipped_count += 1
                continue

            message = build_udhaar_reminder_message(customer)
            sent = send_whatsapp_message(customer.phone, message)

            if sent:
                sent_count += 1
                latest_txn = customer.transactions.first()
                if latest_txn:
                    latest_txn.reminder_sent_at = timezone.now()
                    latest_txn.save()
                self.stdout.write(self.style.SUCCESS(f"Reminder sent to {customer.name}"))
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f"Skipped {customer.name} (no Twilio credentials configured or send failed)")
                )

        self.stdout.write(self.style.SUCCESS(f"\nDone. Sent: {sent_count}, Skipped: {skipped_count}"))
