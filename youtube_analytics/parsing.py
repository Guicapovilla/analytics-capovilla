"""Parse do texto plano `dados.txt` (saída da coleta) para estruturas usadas no dashboard."""


def parsear_dados(texto):
    dados = {}
    secao = ""
    videos_views, videos_receita, receita_diaria = [], [], []
    for linha in texto.split("\n"):
        linha = linha.strip()
        if not linha:
            continue
        if linha.startswith("==="):
            secao = linha
            continue
        if "DADOS DO CANAL" in secao or "ANALYTICS 28 DIAS" in secao:
            if ":" in linha:
                k, v = linha.split(":", 1)
                dados[k.strip()] = v.strip()
        elif "TOP 10 VIDEOS POR VIEWS" in secao:
            if linha and linha[0].isdigit() and "|" in linha:
                parts = linha.split("|")
                titulo = parts[0].split(".", 1)[-1].strip()
                item = {"titulo": titulo}
                for p in parts[1:]:
                    p = p.strip()
                    if "Views:" in p:
                        try:
                            item["views"] = int(p.split(":")[1].strip().replace(",", ""))
                        except Exception:
                            pass
                    elif "Likes:" in p:
                        try:
                            item["likes"] = int(p.split(":")[1].strip().replace(",", ""))
                        except Exception:
                            pass
                    elif "Comentarios:" in p:
                        try:
                            item["comentarios"] = int(p.split(":")[1].strip().replace(",", ""))
                        except Exception:
                            pass
                    elif "Publicado:" in p:
                        try:
                            item["publicado"] = p.split(":", 1)[1].strip()
                        except Exception:
                            pass
                videos_views.append(item)
        elif "TOP 10 VIDEOS POR RECEITA" in secao:
            if linha and linha[0].isdigit() and "|" in linha:
                parts = linha.split("|")
                titulo = parts[0].split(".", 1)[-1].strip()
                item = {"titulo": titulo}
                for p in parts[1:]:
                    p = p.strip()
                    if "BRL:" in p and "R$" in p:
                        try:
                            item["receita"] = float(p.split("R$")[1].strip())
                        except Exception:
                            pass
                    elif "Views:" in p:
                        try:
                            item["views"] = int(p.split(":")[1].strip().replace(",", ""))
                        except Exception:
                            pass
                    elif "RPM:" in p and "R$" in p:
                        try:
                            item["rpm"] = float(p.split("R$")[1].strip())
                        except Exception:
                            pass
                videos_receita.append(item)
        elif "RECEITA DIARIA" in secao:
            if "|" in linha:
                parts = linha.split("|")
                item = {"data": parts[0].strip()}
                for p in parts[1:]:
                    p = p.strip()
                    if "BRL:" in p and "R$" in p:
                        try:
                            item["brl"] = float(p.split("R$")[1].strip())
                        except Exception:
                            pass
                receita_diaria.append(item)
    dados["videos_views"] = videos_views
    dados["videos_receita"] = videos_receita
    dados["receita_diaria"] = receita_diaria
    return dados
