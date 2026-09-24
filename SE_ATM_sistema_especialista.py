import datetime

# ============================================================
# SE-ATM - Sistema Especialista para saque em caixa eletronico
# ============================================================
#
# Um sistema especialista "de verdade" separa o programa em pecas:
#
#   1) Base de Fatos       -> o que a gente sabe da situacao (dict "fatos")
#   2) Base de Regras      -> o conhecimento do especialista, escrito
#                             como regras SE...ENTAO (lista "base_regras")
#   3) Motor de Inferencia -> codigo generico que aplica as regras nos
#                             fatos ate chegar numa conclusao
#   4) Explicacao          -> mostra quais regras foram usadas pra
#                             chegar no resultado (lista "historico")
#
# O script original misturava tudo isso num monte de if/elif com
# estado. Aqui a gente separa: primeiro coleta os fatos do cliente,
# depois o motor de inferencia decide sozinho olhando so pra base
# de regras (ele nao sabe nada de caixa eletronico, so sabe rodar
# a lista de regras).


def pergunta_sim_nao(texto):
    """Pergunta simples de sim/nao. Retorna True ou False."""
    resposta = input(texto + " (s/n): ").strip().lower()
    return resposta == "s"


def pergunta_numero(texto):
    """Pergunta um numero, repetindo ate o usuario digitar certo."""
    while True:
        resposta = input(texto + ": ").strip()
        try:
            return float(resposta)
        except ValueError:
            print("  Digite um numero valido.")


# ------------------------------------------------------------
# 1) BASE DE FATOS (comeca vazia, vai enchendo aos poucos)
# ------------------------------------------------------------
fatos = {}
historico = []  # aqui a gente guarda quais regras dispararam (explicacao)


def concluir(regra_id, mensagem, resultado=None):
    """Registra que uma regra disparou (pra explicacao no final).
    Se 'resultado' for passado, isso fecha o caso e o motor de
    inferencia para de rodar."""
    print(f"  [regra {regra_id}] {mensagem}")
    historico.append(f"{regra_id}: {mensagem}")
    if resultado is not None:
        fatos["resultado"] = resultado


def coletar_fatos_cliente():
    """Fase de entrada: so pergunta pro cliente e guarda em 'fatos'.
    Ainda nao tem regra nenhuma sendo aplicada aqui, e so coleta."""

    input("Pressione ENTER para inserir o cartao...")
    fatos["cartao_bloqueado"] = pergunta_sim_nao("O cartao esta bloqueado ou vencido?")

    if fatos["cartao_bloqueado"]:
        return  # sem cartao valido nao adianta perguntar mais nada

    tentativas = 0
    pin_ok = False
    while tentativas < 3:
        pin_digitado = input("Digite o PIN (use 'errado' pra simular erro): ").strip()
        if pin_digitado.lower() != "errado":
            pin_ok = True
            break
        tentativas += 1
        print(f"PIN incorreto. Tentativa {tentativas}/3.")

    fatos["pin_bloqueado_3x"] = not pin_ok
    if not pin_ok:
        return

    fatos["valor_saque"] = pergunta_numero("Valor do saque (R$)")
    fatos["saldo_suficiente"] = pergunta_sim_nao("Ha saldo suficiente?")
    fatos["dentro_do_limite"] = pergunta_sim_nao("Esta dentro do limite diario?")
    fatos["ha_cedulas"] = pergunta_sim_nao("Ha cedulas disponiveis no terminal?")
    fatos["historico_suspeito"] = pergunta_sim_nao("Ha historico de saques suspeitos?")

    hora_texto = input("Horario da operacao (0-23) [ENTER = agora]: ").strip()
    if hora_texto == "":
        fatos["hora"] = datetime.datetime.now().hour
    else:
        fatos["hora"] = int(hora_texto) % 24


# ------------------------------------------------------------
# 2) BASE DE REGRAS
# ------------------------------------------------------------
# Cada regra tem um "se" (quando ela pode disparar) e um "entao"
# (o que ela faz quando dispara). O motor nem sabe o que e um
# caixa eletronico - ele so sabe rodar essa lista de cima a baixo.

def r1_se(f):
    return "resultado" not in f and f.get("cartao_bloqueado") is True

def r1_entao(f):
    concluir("R1", "Saque negado: cartao bloqueado ou vencido.", "NEGADO")


def r2_se(f):
    return "resultado" not in f and f.get("pin_bloqueado_3x") is True

def r2_entao(f):
    concluir("R2", "Cartao bloqueado: PIN incorreto 3 vezes. Analista antifraude alertado.", "BLOQUEADO")


def r3_se(f):
    return "resultado" not in f and f.get("saldo_suficiente") is False

def r3_entao(f):
    concluir("R3", "Saque negado: saldo insuficiente.", "NEGADO")


def r4_se(f):
    return "resultado" not in f and f.get("dentro_do_limite") is False

def r4_entao(f):
    concluir("R4", "Saque negado: limite diario excedido.", "NEGADO")


def r5_se(f):
    return "resultado" not in f and f.get("ha_cedulas") is False

def r5_entao(f):
    concluir("R5", "Saque negado: sem cedulas disponiveis no terminal.", "NEGADO")


def r6_se(f):
    return "valor_saque" in f and "valor_muito_alto" not in f

def r6_entao(f):
    f["valor_muito_alto"] = f["valor_saque"] > 2000
    texto = "valor acima de R$ 2000" if f["valor_muito_alto"] else "valor dentro do normal"
    concluir("R6", f"Valor do saque analisado ({texto}).")


def r7_se(f):
    return "hora" in f and "horario_atipico" not in f

def r7_entao(f):
    f["horario_atipico"] = f["hora"] < 6 or f["hora"] > 22
    texto = "horario atipico" if f["horario_atipico"] else "horario normal"
    concluir("R7", f"Horario da operacao analisado ({texto}).")


def r8_se(f):
    return ("risco" not in f and f.get("valor_muito_alto") is True
            and (f.get("historico_suspeito") or f.get("horario_atipico")))

def r8_entao(f):
    f["risco"] = "alto"
    concluir("R8", "Risco calculado como ALTO (valor alto + suspeita ou horario atipico).")


def r9_se(f):
    return ("risco" not in f
            and (f.get("historico_suspeito") or f.get("horario_atipico") or f.get("valor_muito_alto")))

def r9_entao(f):
    f["risco"] = "medio"
    concluir("R9", "Risco calculado como MEDIO.")


def rd_se(f):
    # regra padrao (default): se ja sabemos valor e horario e nenhuma
    # regra de risco bateu, assume-se risco baixo. Todo sistema
    # especialista costuma ter uma regra assim pra nao travar sem
    # conclusao quando nada de anormal foi encontrado.
    return "risco" not in f and "valor_muito_alto" in f and "horario_atipico" in f

def rd_entao(f):
    f["risco"] = "baixo"
    concluir("RD", "Nenhuma regra de risco bateu -> risco padrao BAIXO.")


def r10_se(f):
    return "resultado" not in f and f.get("risco") == "alto"

def r10_entao(f):
    concluir("R10", "Risco de fraude alto: saque negado e cartao bloqueado.", "BLOQUEADO")


def r11_se(f):
    return "resultado" not in f and f.get("risco") == "medio" and "verificacao_ok" not in f

def r11_entao(f):
    print("\n[VERIFICANDO] Solicitando biometria ou SMS...")
    aprovada = pergunta_sim_nao("Verificacao adicional aprovada?")
    f["verificacao_ok"] = aprovada
    if aprovada:
        concluir("R11", "Verificacao adicional aprovada.")
    else:
        concluir("R11", "Verificacao adicional nao aprovada.", "NEGADO")


def r12_se(f):
    if "resultado" in f:
        return False
    if f.get("risco") == "baixo":
        return True
    if f.get("risco") == "medio" and f.get("verificacao_ok") is True:
        return True
    return False

def r12_entao(f):
    valor = f.get("valor_saque", 0.0)
    concluir("R12", f"Saque autorizado! Liberando R$ {valor:.2f}.", "AUTORIZADO")


base_regras = [
    {"id": "R1", "se": r1_se, "entao": r1_entao},
    {"id": "R2", "se": r2_se, "entao": r2_entao},
    {"id": "R3", "se": r3_se, "entao": r3_entao},
    {"id": "R4", "se": r4_se, "entao": r4_entao},
    {"id": "R5", "se": r5_se, "entao": r5_entao},
    {"id": "R6", "se": r6_se, "entao": r6_entao},
    {"id": "R7", "se": r7_se, "entao": r7_entao},
    {"id": "R8", "se": r8_se, "entao": r8_entao},
    {"id": "R9", "se": r9_se, "entao": r9_entao},
    {"id": "RD", "se": rd_se, "entao": rd_entao},
    {"id": "R10", "se": r10_se, "entao": r10_entao},
    {"id": "R11", "se": r11_se, "entao": r11_entao},
    {"id": "R12", "se": r12_se, "entao": r12_entao},
]


# ------------------------------------------------------------
# 3) MOTOR DE INFERENCIA (encadeamento para frente)
# ------------------------------------------------------------
def motor_inferencia():
    """Fica passando pela base de regras. Toda vez que uma regra nova
    dispara, os fatos podem mudar, entao a gente varre a lista de
    novo - isso e o 'encadeamento para frente' (forward chaining).
    Para quando ninguem mais dispara ou quando ja tem resultado final."""

    disparadas = set()
    houve_disparo = True

    while houve_disparo and "resultado" not in fatos:
        houve_disparo = False
        for regra in base_regras:
            rid = regra["id"]
            if rid in disparadas:
                continue
            if regra["se"](fatos):
                regra["entao"](fatos)
                disparadas.add(rid)
                houve_disparo = True
                if "resultado" in fatos:
                    break


# ------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():
    print("========================================")
    print(" SE-ATM - Sistema Especialista para saque em caixa eletronico")
    print("========================================\n")

    coletar_fatos_cliente()

    print("\n[MOTOR DE INFERENCIA] Aplicando a base de regras...")
    motor_inferencia()

    print("\n--- Resultado da operacao ---")
    print("Situacao final:", fatos.get("resultado", "INDEFINIDO"))

    print("\n--- Explicacao (regras que dispararam, na ordem) ---")
    for item in historico:
        print(item)


if __name__ == "__main__":
    main()
