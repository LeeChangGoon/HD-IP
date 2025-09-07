"""
URL configuration for rasp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from rfid import user_management, views, views_v2, weight

urlpatterns = [
    
    path('', views.index, name='index'),
    # path('disposal/', views.disposal, name='read_tag'),
    # path('disposal/', views.User_Control.read_tag, name='read_tag'),
    # path('disposal_err_return/', views.disposal_err_return),
    # path('add_user/', views.User_Control.add_user),
    # path('add_card/', views.User_Control.add_card),
    # path('result/', views.Paint_Control.result),
    # path('send_weight/', views.publish_weight),

    # path('home/disposal/', views_v2.disposal),
    # path('disposal/', views_v2.disposal),

    # path('add_card/', views_v2.add_card),
    # path('user_add/', user_management.add_user),
    # path('result/', views_v2.result, name='result'),
    # path('disposal_err/', views_v2.disposal_err),
    # path('home/', views_v2.homePage),

    # path('disposal/<str:uid>/', views_v2.disposal, name='disposal'),  # UID를 처리하는 페이지
    # path('check-rfid-disposal/', views_v2.check_rfid_disposal, name='check_rfid_disposal'),


    # path('home/', rfid_reader.read_card_uid)
    # path('check-rfid-disposal/', views_v2.check_rfid_disposal, name='check_rfid_disposal'),
    # path('result/<str:tag_uid>/', views_v2.result, name='result'),  # UID를 처리하는 페이지


    # RFID 태깅 처리
    path('home/', views_v2.homePage, name='home'),  # 초기 태깅 대기 화면
    path('disposal/<str:uid>/', views_v2.disposal, name='disposal'),  # 태깅 후 이동
    path('check-rfid-disposal/', views_v2.check_rfid_disposal, name='check_rfid_disposal'),  # Ajax RFID 확인
    path('check-rfid/', views_v2.check_rfid, name='check_rfid'),  # RFID 상태 확인 API

    #정보 발행
    path('send_weight/', weight.publish_weight),

    # 사용자 관리
    path('add_card/', views_v2.add_card, name='add_card'),  # 카드 추가 화면
    path('user_add/', user_management.add_user, name='user_add'),  # 사용자 추가 처리
    path('del_card/', views_v2.del_card, name='del_card'),  # 카드 추가 화면

    # 결과 처리
    path('result/', views_v2.result, name='result'),
    # 결과 화면
    path('disposal_err/', views_v2.disposal_err, name='disposal_err'),  # 에러 처리
    # 기타
    path('home/disposal/', views_v2.disposal, name='home_disposal'),  # 추가 경로 (필요하면 유지)

]

