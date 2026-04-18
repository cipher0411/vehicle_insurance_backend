# apps/core/management/commands/process_auto_debits.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.views import run_auto_debit_job
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process auto-debit for due installments'

    def handle(self, *args, **options):
        self.stdout.write('Starting auto-debit processing...')
        
        try:
            results = run_auto_debit_job()
            
            success_count = sum(1 for r in results if r['success'])
            fail_count = len(results) - success_count
            
            self.stdout.write(self.style.SUCCESS(
                f'Auto-debit completed. Success: {success_count}, Failed: {fail_count}'
            ))
            
            for result in results:
                if not result['success']:
                    self.stdout.write(self.style.WARNING(
                        f"Failed: {result['installment_id']} - {result['message']}"
                    ))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            logger.error(f"Auto-debit job error: {str(e)}")
            
            
            
            
            
            
            
            
            
# # Run auto-debit daily at 8:00 AM
#  0 8 * * * cd /path/to/your/project && /path/to/venv/bin/python manage.py process_auto_debits >> /var/log/auto_debit.log 2>&1