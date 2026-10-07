"""Registro de atendimento (T16): quanto custa levar uma caldeira do primeiro envio ao
primeiro fechamento, medido nos registros da própria planta.

Tudo vem do log de eventos do armazém (lote importado, referência criada, fechamento
produzido) e da medição que a tela grava em cada envio (`segundos_na_tela`, `ajustes`).
Nada é estimado: envio sem medição é contado como "sem medição", nunca como zero.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from euler.armazem import Armazem


def _instante(evento: dict | None) -> datetime | None:
    return datetime.fromisoformat(evento["quando"]) if evento else None


def registro_atendimento(a: Armazem, equip_id: str) -> dict:
    """Resumo do caminho do primeiro envio ao primeiro fechamento de um equipamento.

    Saída (tudo medido; None quando ainda não aconteceu ou não foi medido):
    - primeiro_envio, referencia, primeiro_fechamento: instantes (ISO, UTC) dos eventos;
    - horas_ate_primeiro_fechamento: tempo de calendário entre o primeiro envio e o primeiro
      fechamento (inclui esperas fora da EULER, como juntar mais semanas de dados);
    - envios_ate_fechamento: lotes importados até o primeiro fechamento;
    - envios_medidos / envios_sem_medicao: quantos desses lotes têm a medição da tela;
    - segundos_na_tela: soma do tempo medido na tela de envio (do arquivo à confirmação,
      incluindo pausas), só dos envios medidos;
    - ajustes: soma dos campos que a pessoa precisou alterar ou preencher, só dos envios
      em que a conferência guiada guardou o que foi sugerido;
    - envios: lista por lote (instante, segundos_na_tela, ajustes).
    """
    eventos = sorted(a.eventos(equip_id, limite=100_000), key=lambda e: e["id"])
    eventos = [e for e in eventos if e["equipamento_id"] == equip_id]
    lotes = [e for e in eventos if (e["entidade"], e["tipo"]) == ("lote", "importado")]
    referencia = next(
        (e for e in eventos if (e["entidade"], e["tipo"]) == ("referencia", "criada")), None
    )
    fechamento = next(
        (e for e in eventos if (e["entidade"], e["tipo"]) == ("fechamento", "produzido")), None
    )
    antes = [e for e in lotes if fechamento is None or e["id"] < fechamento["id"]]
    envios = []
    for e in antes:
        medido = e["dados"].get("atendimento") or {}
        envios.append(
            {
                "quando": e["quando"],
                "segundos_na_tela": medido.get("segundos_na_tela"),
                "ajustes": (medido.get("ajustes") or {}).get("total"),
            }
        )
    medidos = [x["segundos_na_tela"] for x in envios if x["segundos_na_tela"] is not None]
    com_ajustes = [x["ajustes"] for x in envios if x["ajustes"] is not None]
    inicio, fim = _instante(lotes[0] if lotes else None), _instante(fechamento)
    return {
        "primeiro_envio": lotes[0]["quando"] if lotes else None,
        "referencia": referencia["quando"] if referencia else None,
        "primeiro_fechamento": fechamento["quando"] if fechamento else None,
        "horas_ate_primeiro_fechamento": (
            round((fim - inicio).total_seconds() / 3600, 2) if inicio and fim else None
        ),
        "envios_ate_fechamento": len(antes),
        "envios_medidos": len(medidos),
        "envios_sem_medicao": len(antes) - len(medidos),
        "segundos_na_tela": round(sum(medidos), 1) if medidos else None,
        "ajustes": sum(com_ajustes) if com_ajustes else None,
        "envios": envios,
    }


def atendimentos_registrados(a: Armazem, equip_id: str) -> list[dict]:
    """Horas da equipe lançadas à mão para este equipamento (T16), do mais antigo ao mais novo."""
    eventos = sorted(a.eventos(equip_id, limite=100_000), key=lambda e: e["id"])
    return [
        {**e["dados"], "autor": e["autor"], "lancado_em": e["quando"]}
        for e in eventos
        if e["equipamento_id"] == equip_id
        and (e["entidade"], e["tipo"]) == ("atendimento", "registrado")
    ]


def minutos_por_mes(registros: list[dict]) -> dict[str, dict]:
    """{"AAAA-MM": {"minutos": total, "por_tarefa": {tarefa: minutos}}}, só do que foi lançado."""
    out: dict[str, dict] = {}
    for r in registros:
        mes = out.setdefault(r["dia"][:7], {"minutos": 0.0, "por_tarefa": {}})
        mes["minutos"] += r["minutos"]
        mes["por_tarefa"][r["tarefa"]] = mes["por_tarefa"].get(r["tarefa"], 0.0) + r["minutos"]
    return dict(sorted(out.items()))


def _celula(texto) -> str:
    """Texto que uma planilha não executa como fórmula ("=…", "+…", "-…", "@…")."""
    t = str(texto)
    return "'" + t if t[:1] in {"=", "+", "-", "@"} else t


def csv_atendimento(cliente: str, equip_id: str, registros: list[dict]) -> bytes:
    """`atendimento.csv` do T16: cliente, equipamento, data, tarefa, minutos, quem, nota."""
    linhas = io.StringIO()
    w = csv.writer(linhas, lineterminator="\n")
    w.writerow(["cliente", "equipamento_id", "data", "tarefa", "minutos", "autor", "nota"])
    for r in registros:
        w.writerow(
            [
                _celula(cliente),
                _celula(equip_id),
                r["dia"],
                r["tarefa"],
                r["minutos"],
                _celula(r["autor"]),
                _celula(r.get("nota", "")),
            ]
        )
    return linhas.getvalue().encode("utf-8")
