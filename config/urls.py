from django.contrib import admin
from django.urls import path
from core.news_api import market_news_api
from core import views
from core.chart_api import chart_symbol_api
from core.top_stocks_api import top_stocks_api

from sentinel.views import analyze_biometrics


urlpatterns = [

    # =====================================================
    # ADMIN
    # =====================================================

    path(
        'admin/',
        admin.site.urls,
    ),


    # =====================================================
    # MAIN UI
    # =====================================================

    path(
        '',
        views.landing,
        name='landing',
    ),

    path(
        'dashboard/',
        views.dashboard,
        name='dashboard',
    ),


    # =====================================================
    # AI ROUTES
    # =====================================================

    path(
        'get-ai-insight/',
        views.get_ai_insight,
        name='ai_insight_legacy',
    ),

    path(
        'api/ai-insight/',
        views.get_ai_insight,
        name='ai_insight',
    ),


    # =====================================================
    # MARKET DATA
    # =====================================================

    path(
        'api/market-data/',
        views.get_market_data,
        name='market_data',
    ),

   path(
        'api/market-news/',
        market_news_api,
        name='market_news',
    ),


    # =====================================================
    # TOP 10 STOCK ENGINE
    # =====================================================

    path(
        'api/top-stocks/',
        top_stocks_api,
        name='top_stocks_api',
    ),


    # =====================================================
    # TRADINGVIEW CHART SYMBOL API
    # =====================================================

    path(
        'api/chart-symbol/',
        chart_symbol_api,
        name='chart_symbol_api',
    ),


    # =====================================================
    # BIOMETRICS
    # =====================================================

    path(
        'sentinel/analyze/',
        analyze_biometrics,
        name='analyze_biometrics',
    ),


    # =====================================================
    # TRADINGVIEW WEBHOOK
    # =====================================================

    path(
        'webhook/tv/',
        views.tradingview_webhook,
        name='tradingview_webhook',
    ),
]