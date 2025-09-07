from django.db import models
from django.forms import ValidationError

# Create your models here.


# Weight_v3 모델
class Weight_v3(models.Model):
    asgn_cd = models.IntegerField(primary_key=True)  # 고유 값으로 변경
    company = models.CharField(max_length=25) # 회사명 추가
    weight = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.asgn_cd}: {self.weight}kg"

    def clean(self):
        if self.weight < 0:
            raise ValidationError("Weight must be a positive value.")


# User_v3 모델
class User_v3(models.Model):
    uid = models.CharField(max_length=255, primary_key=True)  # UID
    name = models.CharField(max_length=255)
    asgn_cd = models.ForeignKey(Weight_v3, on_delete=models.CASCADE)  # 1:N 관계
    depart = models.CharField(max_length=25, default="Unknown")
    company = models.CharField(max_length=25, default="Unknown")
    
    def __str__(self):
        return self.name