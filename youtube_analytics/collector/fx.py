import requests


def cotacao_usd():
    try:
        r = requests.get('https://economia.awesomeapi.com.br/json/last/USD-BRL', timeout=5)
        return float(r.json()['USDBRL']['bid'])
    except Exception:
        try:
            r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5)
            return float(r.json()['rates']['BRL'])
        except Exception:
            return 5.26
