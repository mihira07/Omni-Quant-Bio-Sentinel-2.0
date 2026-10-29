from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from core import views
from core.chart_api import chart_symbol_api
from core.chart_data_api import chart_data_api
from core.chat_api import chat_api
from core.top_stocks_api import top_stocks_api

from sentinel.views import analyze_biometrics


urlpatterns = [
    path("admin/", admin.site.urls),

    # Authentication
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # Landing / boot menu and main dashboard
    path(
        "",
        login_required(views.landing),
        name="landing",
    ),
    path(
        "dashboard/",
        login_required(views.dashboard),
        name="dashboard",
    ),

    # AI analysis and chatbot
    path(
        "get-ai-insight/",
        views.get_ai_insight,
        name="ai_insight_legacy",
    ),
    path(
        "api/ai-insight/",
        views.get_ai_insight,
        name="ai_insight",
    ),
    path(
        "api/chat/",
        login_required(chat_api),
        name="chat_api",
    ),

    # Market data / news
    path(
        "api/market-data/",
        views.get_market_data,
        name="market_data",
    ),
    path(
        "api/market-news/",
        views.get_market_news,
        name="market_news",
    ),
    path(
        "api/top-stocks/",
        top_stocks_api,
        name="top_stocks_api",
    ),

    # TradingView symbol resolution and historical chart fallback
    path(
        "api/chart-symbol/",
        chart_symbol_api,
        name="chart_symbol_api",
    ),
    path(
        "api/chart-data/",
        login_required(chart_data_api),
        name="chart_data_api",
    ),

    # Bio-Sentinel
    path(
        "sentinel/analyze/",
        login_required(analyze_biometrics),
        name="analyze_biometrics",
    ),

    # TradingView webhook
    path(
        "webhook/tv/",
        views.tradingview_webhook,
        name="tradingview_webhook",
    ),
]