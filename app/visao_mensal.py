"""Escolhas de apresentação do ciclo mensal; não calcula nem altera a conta."""

from euler.mensal import chave_do_mes


def mes_em_foco(planos: list[dict]) -> dict | None:
    """Prioriza pendências cronológicas; nunca seleciona pelo valor do resultado."""
    return next(
        (x for x in planos if x["estado"] in ("revisar", "pronto")),
        next(
            (x for x in reversed(planos) if x["estado"] == "fechado"),
            planos[-1] if planos else None,
        ),
    )


def fechamentos_do_mes(vigentes: list[dict], mes: str) -> list[dict]:
    """Mantém também lacunas e fechamentos legados que terminam no mês escolhido."""
    return [f for f in vigentes if (f["resultado"].get("mes") or chave_do_mes(f["fim"])) == mes]


def orientacao_do_mes(estado: str) -> tuple[str, str]:
    """Próximo passo a partir do estado persistido, sem prometer economia."""
    return {
        "pronto": (
            "Conferir e fechar",
            "Confira a prévia e as lacunas; depois aprove o mês com seu nome.",
        ),
        "revisar": (
            "Revisar o mês",
            "Um registro mudou. Confira a nova conta e registre o motivo da revisão.",
        ),
        "aguarda_anterior": (
            "Concluir o mês anterior",
            "Feche os meses em ordem para preservar a continuidade do histórico.",
        ),
        "em_andamento": (
            "Atualizar os registros",
            "Envie os novos registros. A aprovação fica disponível depois do fim do mês.",
        ),
        "sem_periodo": (
            "Completar os dados",
            "Confira a referência e as medições de estoque. Sem período completo não há conta do mês.",
        ),
        "referencia": (
            "Base de comparação",
            "Este mês faz parte da referência; não representa um resultado mensal de economia.",
        ),
        "fechado": (
            "Acompanhar as ações",
            "O mês está registrado. Acompanhe as verificações e prepare os dados do próximo mês.",
        ),
    }[estado]
