"""Adapters de dados para o componente de dashboard."""

from __future__ import annotations

from datetime import datetime


def normalize_funil(funil_json: dict) -> dict:
    out = {}
    total = 0
    for etapa in ("topo", "meio", "fundo"):
        videos = funil_json.get(etapa, [])
        if isinstance(videos, list):
            count = len(videos)
            receita = sum(v.get("receita", 0) for v in videos)
            rpm_sum = sum(v.get("rpm", 0) for v in videos)
            rpm_med = rpm_sum / count if count else 0
        else:
            count = receita = rpm_med = 0
        out[etapa] = {"count": count, "rpm_medio": round(rpm_med, 2), "receita": round(receita, 2)}
        total += count
    lacuna_raw = funil_json.get("lacuna", funil_json.get("lacuna_descricao", ""))
    out["lacuna"] = lacuna_raw or "nenhuma"
    out["lacuna_descricao"] = funil_json.get("lacuna_descricao", lacuna_raw or "Funil equilibrado")
    out["total"] = total
    return out


def normalize_fila(fila_json: list, historico: list | None, find_historico_video_match) -> list:
    result = []
    status_map = {"planejado": "planejado", "gravando": "gravando", "publicado": "publicado", "concluido": "concluido"}
    hist = historico if isinstance(historico, list) else []
    for item in fila_json:
        titulo = item.get("titulo_publicado") or item.get("titulo_planejado", "")
        h_match = find_historico_video_match(hist, item) if hist else None
        linked_sug_id = ""
        has_notas_criador = False
        if isinstance(h_match, dict):
            linked_sug_id = str(h_match.get("sugestao_id") or "").strip()
            has_notas_criador = bool(str(h_match.get("notas_criador") or "").strip())
        is_linked = bool(linked_sug_id or has_notas_criador)
        result.append(
            {
                "id": item.get("sugestao_id") or f"item-{len(result)+1}",
                "sugestao_id": item.get("sugestao_id"),
                "titulo": titulo,
                "rpm": item.get("rpm_previsto", 0),
                "funil": item.get("funil", "topo"),
                "status": status_map.get(item.get("status", "planejado"), "planejado"),
                "origem": item.get("origem", "ideia_propria"),
                "data": (item.get("data_publicacao") or item.get("data_planejamento", ""))[:10],
                "views": item.get("views", 0),
                "video_id": item.get("video_id_youtube", ""),
                "is_linked_real": is_linked,
                "linked_sugestao_id": linked_sug_id,
            }
        )
    return result


def dados_para_componente(dados_parsed: dict) -> dict:
    def _int(k):
        try:
            return int(str(dados_parsed.get(k, 0) or 0).replace(",", "").replace(".", "").split()[0])
        except Exception:
            return 0

    def _float(k):
        try:
            return float(str(dados_parsed.get(k, 0) or 0).replace(",", ".").replace("R$", "").strip())
        except Exception:
            return 0.0

    inscritos = _int("Inscritos")
    views_totais = _int("Views totais")
    total_videos = _int("Total de vídeos") or _int("Total videos") or _int("Videos")
    views_28d = _int("Views")
    horas_28d = _float("Horas assistidas")
    novos = _int("Novos inscritos")
    receita_brl = _float("Receita BRL")
    cotacao = _float("Cotação USD/BRL") or 5.15

    top_rpm = []
    for v in dados_parsed.get("videos_receita", [])[:10]:
        top_rpm.append({"titulo": v.get("titulo", ""), "brl": v.get("receita", 0), "views": v.get("views", 0), "rpm": v.get("rpm", 0)})

    receita_diaria = []
    for r in dados_parsed.get("receita_diaria", []):
        receita_diaria.append({"d": r.get("data", ""), "brl": r.get("brl", 0)})

    console_map = {}
    for v in dados_parsed.get("videos_receita", []):
        titulo = (v.get("titulo") or "").lower()
        rec = v.get("receita", 0)
        if "switch" in titulo:
            console_map["Switch"] = console_map.get("Switch", 0) + rec
        elif "ps4" in titulo or "playstation 4" in titulo:
            console_map["PS4"] = console_map.get("PS4", 0) + rec
        elif "steam deck" in titulo:
            console_map["Steam Deck"] = console_map.get("Steam Deck", 0) + rec
        elif "xbox" in titulo:
            console_map["Xbox"] = console_map.get("Xbox", 0) + rec
        else:
            console_map["Outros"] = console_map.get("Outros", 0) + rec
    total_console = sum(console_map.values()) or 1
    receita_console = [{"console": k, "receita": round(v, 2), "pct": round(v / total_console * 100)} for k, v in sorted(console_map.items(), key=lambda x: -x[1])]

    return {
        "canal": {"inscritos": inscritos, "views_totais": views_totais, "total_videos": total_videos, "cotacao": cotacao},
        "analytics28d": {"views": views_28d, "horas": horas_28d, "novos_inscritos": novos, "receita_brl": receita_brl},
        "top_rpm": top_rpm,
        "receita_diaria": receita_diaria,
        "receita_console": receita_console,
    }


def parse_receita_day(raw_day: str, ref_year: int):
    if not raw_day:
        return None
    txt = str(raw_day).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    try:
        d = datetime.strptime(txt, "%d/%m").date()
        return d.replace(year=ref_year)
    except ValueError:
        return None


def calcular_receita_trimestre_atual(receita_diaria: list) -> tuple:
    now_utc = datetime.utcnow()
    q_start_month = ((now_utc.month - 1) // 3) * 3 + 1
    q_end_month = q_start_month + 2
    total = 0.0
    has_points = False
    for row in receita_diaria or []:
        if not isinstance(row, dict):
            continue
        day = parse_receita_day(row.get("d", ""), now_utc.year)
        if day is None:
            continue
        if day.year == now_utc.year and q_start_month <= day.month <= q_end_month:
            try:
                total += float(row.get("brl", 0) or 0)
                has_points = True
            except (TypeError, ValueError):
                continue
    return round(total, 2), has_points


def metas_para_componente(metas_json: dict, historico: list, receita_q2_calculada=None, receita_q2_has_data=False) -> dict:
    m = metas_json
    vinculados = [h for h in historico if h.get("sugestao_id") and h.get("rpm_real") is not None and h.get("rpm_previsto")]
    acertos = sum(1 for h in vinculados if h.get("rpm_real", 0) >= h.get("rpm_previsto", 1) * 0.7)
    pct_acerto = round(acertos / len(vinculados) * 100) if vinculados else 0
    receita_q2_valor = receita_q2_calculada if receita_q2_calculada is not None else m.get("receita_q2", 0)
    return {
        "anual": {"desc": m.get("meta_anual_desc", m.get("descricao", "—")), "atingida": m.get("meta_anual_atingida", False)},
        "ano": {"receita": m.get("receita_ano", m.get("meta_receita_anual", 30000)), "inscritos": m.get("inscritos_ano", m.get("meta_inscritos_anual", 10000)), "videos": m.get("videos_ano", m.get("meta_videos_anual", 52))},
        "q2": {"receita": m.get("meta_receita_q2", 8000), "inscritos": m.get("meta_inscritos_q2", 3000), "videos": m.get("meta_videos_q2", 13)},
        "atual": {
            "receita_ytd": m.get("receita_ytd", 0),
            "inscritos_ytd": m.get("inscritos_ytd", 0),
            "videos_ytd": m.get("videos_ytd", 0),
            "receita_q2": receita_q2_valor,
            "receita_q2_has_data": bool(receita_q2_has_data),
            "inscritos_q2": m.get("inscritos_q2", 0),
            "videos_q2": m.get("videos_q2", 0),
        },
        "accuracy": {"overall": pct_acerto, "trend": f"+{pct_acerto}% (histórico)", "months": []},
        "padroes": m.get("padroes", []),
    }


def historico_links(historico: list, sugestoes_pendentes: list) -> list:
    sug_map = {s.get("id", ""): s for s in sugestoes_pendentes}
    links = []
    for h in historico[-10:]:
        sug_id = h.get("sugestao_id", "")
        sug_obj = sug_map.get(sug_id, {})
        sug_text = sug_obj.get("texto") or sug_id or "Manual"
        rpm_real = h.get("rpm_real", 0)
        rpm_prev = h.get("rpm_previsto", 0)
        ok_val = None
        if rpm_real and rpm_prev:
            ok_val = rpm_real >= rpm_prev * 0.7
        links.append({"video": h.get("titulo", h.get("titulo_video", ""))[:40], "sug": sug_text[:40], "rpm_real": rpm_real, "rpm_prev": rpm_prev, "ok": ok_val})
    return links


def config_status(carregar_arquivo, github_token: str, aprendizados_file: str) -> dict:
    files_to_check = [
        "dados.txt",
        "concorrentes.json",
        "historico.json",
        "funil.json",
        "transcricoes_canal.json",
        "fila_producao.json",
        "sugestoes_pendentes.json",
        "sugestao_semana.json",
        "contexto.txt",
        "metas.json",
        aprendizados_file,
    ]
    now_str = datetime.now().strftime("%d/%m %H:%M")
    files_status = []
    for fname in files_to_check:
        status = "ok" if carregar_arquivo(fname, None) is not None else "err"
        files_status.append({"name": fname, "status": status, "update": now_str})
    token_ok = bool(github_token)
    return {
        "token": {
            "status": "ok" if token_ok else "err",
            "expira": "—",
            "msg": "Token configurado" if token_ok else "Token ausente — configure nas Secrets",
        },
        "files": files_status,
    }

