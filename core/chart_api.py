from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .tradingview_symbols import resolve_tradingview_symbol


@require_GET
def chart_symbol_api(request):

    segment = request.GET.get(
        'segment',
        'STOCKS',
    )

    symbol = request.GET.get(
        'symbol',
        '',
    )

    result = resolve_tradingview_symbol(
        segment=segment,
        symbol=symbol,
    )

    if result.get('status') == 'ERROR':
        return JsonResponse(
            result,
            status=400,
        )

    return JsonResponse(
        result,
        status=200,
    )