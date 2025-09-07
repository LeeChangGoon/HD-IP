from django.core.management.base import BaseCommand
from rfid.models import Weight

class Command(BaseCommand):
    help = "폐기량 테이블을 매달 초기화합니다."

    def handle(self, *args, **options):
        Weight.objects.all().update(weight=0)
        self.stdout.write(self.style.SUCCESS("폐기량 테이블이 초기화되었습니다."))
