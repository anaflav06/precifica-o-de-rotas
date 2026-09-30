import json
import base64
import requests
from pathlib import Path
from datetime import datetime
from io import BytesIO

import streamlit as st

# PDF é opcional no carregamento; o app continua abrindo mesmo se reportlab não estiver instalado.
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False


# =========================================================
# CONFIGURAÇÃO GERAL
# =========================================================
st.set_page_config(
    page_title="GDS | Precificação de Rotas",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _secret(nome, padrao=None):
    try:
        return st.secrets.get(nome, padrao)
    except Exception:
        return padrao

APP_PASSWORD = _secret("APP_PASSWORD", "gds@9129")
PARAMS_PATH = Path("parametros_precificacao.json")
HISTORY_PATH = Path("historico_cotacoes.json")

GITHUB_TOKEN = _secret("GITHUB_TOKEN", "")
GITHUB_REPO = _secret("GITHUB_REPO", "")
GITHUB_DATA_BRANCH = _secret("GITHUB_DATA_BRANCH", "main")
GITHUB_PARAMS_PATH = _secret("GITHUB_PARAMS_PATH", "data/parametros_precificacao.json")
GITHUB_HISTORY_PATH = _secret("GITHUB_HISTORY_PATH", "data/historico_cotacoes.json")
USE_GITHUB_DB = bool(GITHUB_TOKEN and GITHUB_REPO)

DEFAULTS = {
    "diesel_litro": 7.35,
    "consumo_km_l": 2.5,
    "arla_litro": 3.50,
    "diesel_por_litro_arla": 20.0,
    "manutencao_km": 0.20,
    "pneus_km": 0.15,
    "outros_variaveis_viagem": 80.00,
    "depreciacao_viagem": 500.00,
    "salario_motorista_viagem": 150.00,
    "encargos_motorista_viagem": 105.00,
    "seguro_viagem": 50.00,
    "despesas_adm_viagem": 450.00,
    "outras_fixas_viagem": 30.00,
    "markup_percentual": 20.0,
    "frete_minimo": 0.00,
    "impostos_percentual": 0.0,
    "hora_parada": 0.00,
    "validade_cotacao_dias": 7,
}

VEICULOS = [
    "Carreta", "Truck", "Toco", "3/4", "VUC", "Van", "Fiorino", "Outro"
]
STATUS_COTACAO = ["Em análise", "Enviada", "Aprovada", "Reprovada", "Cancelada"]

# =========================================================
# ESTILO GDS
# =========================================================
st.markdown(
    """
<style>
:root {
    --orange:#ff6a00;
    --orange2:#ff9b4a;
    --black:#0d0d0d;
    --dark:#1b1b1d;
    --gray:#707070;
    --light:#f3f4f6;
    --white:#ffffff;
}

.stApp {
    background: radial-gradient(circle at top right, #fff6ef 0, #f7f7f7 22%, #eeeeee 100%);
}
.block-container {padding-top:1.2rem; padding-bottom:2.5rem; max-width:1550px;}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#080808 0%,#1d1d1f 58%,#3a1b06 100%);
    border-right:1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] * {color:white;}

.brand {font-weight:950;font-size:1.65rem;letter-spacing:.6px;margin:.15rem 0 0 0;}
.brand span {color:var(--orange);}
.brand-sub {font-size:.78rem;color:#bdbdbd;margin-bottom:1.1rem;}

.hero {
    background: linear-gradient(110deg,#101010 0%,#292929 67%,#ff6a00 155%);
    color:white;border-radius:24px;padding:25px 28px;margin-bottom:18px;
    box-shadow:0 14px 35px rgba(0,0,0,.12);
}
.hero h1{font-size:2rem;margin:0;font-weight:900;}
.hero p{color:#d4d4d4;margin:.35rem 0 0;}

.menu-card {
    border-radius:20px;padding:18px;color:white;min-height:118px;
    background:linear-gradient(135deg,#181818,#343434 72%,#ff6a00 150%);
    box-shadow:0 10px 25px rgba(0,0,0,.09);border:1px solid rgba(255,255,255,.08);
}
.menu-card .icon{font-size:1.55rem;}.menu-card .title{font-size:1.05rem;font-weight:850;margin-top:5px;}
.menu-card .desc{font-size:.78rem;color:#d5d5d5;margin-top:4px;}

.panel {
    background:rgba(255,255,255,.97);border:1px solid #e5e5e5;border-radius:20px;
    padding:18px 20px;box-shadow:0 8px 24px rgba(0,0,0,.05);margin-bottom:14px;
}

.kpi {
    background:linear-gradient(140deg,#121212,#2a2a2a 78%,#5a2800 150%);
    color:white;border-radius:18px;padding:17px 18px;min-height:120px;
    box-shadow:0 8px 22px rgba(0,0,0,.10);
}
.kpi .label{font-size:.78rem;color:#c8c8c8;}.kpi .value{font-size:1.7rem;font-weight:900;margin-top:5px;}
.kpi .sub{font-size:.74rem;color:#a8a8a8;margin-top:5px;}

.quote-row {
    background:white;border:1px solid #e6e6e6;border-left:5px solid var(--orange);
    border-radius:16px;padding:13px 16px;margin:.45rem 0;
}
.quote-row .qtitle{font-weight:850;color:#1c1c1c;}.quote-row .qmeta{color:#686868;font-size:.82rem;margin-top:3px;}

.login-box {
    max-width:430px;margin:8vh auto 0;background:white;border:1px solid #e3e3e3;
    border-radius:25px;padding:30px;box-shadow:0 18px 48px rgba(0,0,0,.12);
}
.login-title{text-align:center;font-weight:950;font-size:2rem;}.login-title span{color:var(--orange);}
.login-sub{text-align:center;color:#777;font-size:.84rem;margin-bottom:18px;}

[data-testid="stSidebar"] div.stButton > button {
    width:100%;justify-content:flex-start;text-align:left;min-height:50px;
    border-radius:15px;margin-bottom:.35rem;padding:.75rem .9rem;font-weight:800;
    background:linear-gradient(120deg,rgba(255,255,255,.07),rgba(255,106,0,.11));
    border:1px solid rgba(255,255,255,.10);color:white;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    border-color:#ff6a00;background:linear-gradient(120deg,rgba(255,106,0,.22),rgba(255,255,255,.08));
}

div.stButton > button {border-radius:13px;min-height:43px;font-weight:800;}
div.stButton > button[kind="primary"] {
    background:linear-gradient(90deg,#ff6a00,#ff8d31);border:none;color:white;
    box-shadow:0 7px 17px rgba(255,106,0,.22);
}
[data-testid="stMetric"]{background:white;border:1px solid #e7e7e7;padding:12px 15px;border-radius:15px;}
.small{color:#777;font-size:.78rem;}
hr{border-color:#ececec;}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# FUNÇÕES DE DADOS
# =========================================================
def read_json_local(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_local(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def github_get_json(repo_path, default):
    if not USE_GITHUB_DB:
        return default
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        r = requests.get(url, headers=headers, params={"ref": GITHUB_DATA_BRANCH}, timeout=20)
        if r.status_code == 404:
            return default
        r.raise_for_status()
        payload = r.json()
        raw = base64.b64decode(payload.get("content", "")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return default


def github_put_json(repo_path, data, message):
    if not USE_GITHUB_DB:
        return False, "GitHub não configurado"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    sha = None
    try:
        current = requests.get(url, headers=headers, params={"ref": GITHUB_DATA_BRANCH}, timeout=20)
        if current.status_code == 200:
            sha = current.json().get("sha")
        elif current.status_code != 404:
            current.raise_for_status()

        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        body = {
            "message": message,
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": GITHUB_DATA_BRANCH,
        }
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=headers, json=body, timeout=20)
        r.raise_for_status()
        return True, ""
    except Exception as e:
        return False, str(e)


def carregar_parametros():
    if USE_GITHUB_DB:
        data = github_get_json(GITHUB_PARAMS_PATH, {})
    else:
        data = read_json_local(PARAMS_PATH, {})
    out = DEFAULTS.copy()
    if isinstance(data, dict):
        out.update(data)
    if float(out.get("diesel_litro", 7.35)) == 7.00:
        out["diesel_litro"] = 7.35
    return out


def salvar_parametros(data):
    data = dict(data)
    data["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    if USE_GITHUB_DB:
        ok, erro = github_put_json(GITHUB_PARAMS_PATH, data, "Atualiza parâmetros de precificação")
        if not ok:
            raise RuntimeError(erro)
    else:
        write_json_local(PARAMS_PATH, data)


def carregar_historico():
    if USE_GITHUB_DB:
        data = github_get_json(GITHUB_HISTORY_PATH, [])
    else:
        data = read_json_local(HISTORY_PATH, [])
    return data if isinstance(data, list) else []


def salvar_historico(lista):
    if USE_GITHUB_DB:
        ok, erro = github_put_json(GITHUB_HISTORY_PATH, lista, "Atualiza histórico de cotações")
        if not ok:
            raise RuntimeError(erro)
    else:
        write_json_local(HISTORY_PATH, lista)


def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def fmt(v, casas=2):
    try:
        return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def normalizar_cep(cep):
    d = "".join(c for c in str(cep) if c.isdigit())
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return str(cep).strip()


def proximo_numero(historico):
    ano = datetime.now().year
    nums = []
    prefix = f"COT-{ano}-"
    for q in historico:
        n = str(q.get("numero", ""))
        if n.startswith(prefix):
            try:
                nums.append(int(n.split("-")[-1]))
            except Exception:
                pass
    return f"COT-{ano}-{(max(nums) + 1 if nums else 1):04d}"


def calcular_cotacao(p, km_ida, usar_volta_km, km_volta, pedagio_ida, usar_volta_pedagio,
                     pedagio_volta, adicional_valor, adicional_percentual, horas_paradas=0.0):
    km_total = float(km_ida) + (float(km_volta) if usar_volta_km else 0.0)
    pedagio_total = float(pedagio_ida) + (float(pedagio_volta) if usar_volta_pedagio else 0.0)

    consumo = max(float(p["consumo_km_l"]), 0.0001)
    diesel_litros = km_total / consumo
    custo_diesel = diesel_litros * float(p["diesel_litro"])

    razao_arla = max(float(p["diesel_por_litro_arla"]), 0.0001)
    arla_litros = diesel_litros / razao_arla
    custo_arla = arla_litros * float(p["arla_litro"])

    custo_manutencao = km_total * float(p["manutencao_km"])
    custo_pneus = km_total * float(p["pneus_km"])
    outros_variaveis = float(p["outros_variaveis_viagem"])
    custo_horas_paradas = float(horas_paradas) * float(p.get("hora_parada", 0.0))

    fixos = {
        "Depreciação": float(p["depreciacao_viagem"]),
        "Salário motorista": float(p["salario_motorista_viagem"]),
        "Encargos motorista": float(p["encargos_motorista_viagem"]),
        "Seguro veículo": float(p["seguro_viagem"]),
        "Despesas administrativas": float(p["despesas_adm_viagem"]),
        "Outras despesas fixas": float(p["outras_fixas_viagem"]),
    }
    total_fixos = sum(fixos.values())

    subtotal_base = (
        custo_diesel + custo_arla + custo_manutencao + custo_pneus + outros_variaveis +
        pedagio_total + custo_horas_paradas + total_fixos + float(adicional_valor)
    )
    adicional_pct_valor = subtotal_base * (float(adicional_percentual) / 100.0)
    custo_operacional = subtotal_base + adicional_pct_valor

    markup_valor = custo_operacional * (float(p["markup_percentual"]) / 100.0)
    venda_antes_imposto = custo_operacional + markup_valor
    imposto_valor = venda_antes_imposto * (float(p.get("impostos_percentual", 0.0)) / 100.0)
    preco_calculado = venda_antes_imposto + imposto_valor
    preco_final = max(preco_calculado, float(p.get("frete_minimo", 0.0)))

    return {
        "km_total": km_total,
        "pedagio_total": pedagio_total,
        "diesel_litros": diesel_litros,
        "custo_diesel": custo_diesel,
        "arla_litros": arla_litros,
        "custo_arla": custo_arla,
        "custo_manutencao": custo_manutencao,
        "custo_pneus": custo_pneus,
        "outros_variaveis": outros_variaveis,
        "custo_horas_paradas": custo_horas_paradas,
        "fixos": fixos,
        "total_fixos": total_fixos,
        "adicional_valor": float(adicional_valor),
        "adicional_percentual": float(adicional_percentual),
        "adicional_pct_valor": adicional_pct_valor,
        "custo_operacional": custo_operacional,
        "markup_percentual": float(p["markup_percentual"]),
        "markup_valor": markup_valor,
        "impostos_percentual": float(p.get("impostos_percentual", 0.0)),
        "imposto_valor": imposto_valor,
        "preco_calculado": preco_calculado,
        "preco_final": preco_final,
        "valor_km": (preco_final / km_total) if km_total > 0 else 0.0,
    }


# =========================================================
# PDFs
# =========================================================
def _pdf_header(canvas, doc, titulo):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#111111"))
    canvas.rect(0, A4[1]-28*mm, A4[0], 28*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#ff6a00"))
    canvas.rect(0, A4[1]-29.5*mm, A4[0], 1.5*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(15*mm, A4[1]-17*mm, "GDS - Precificacao de Rotas")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0]-15*mm, A4[1]-17*mm, titulo)
    canvas.restoreState()


def gerar_pdf_cliente(q):
    if not REPORTLAB_OK:
        return None
    bio = BytesIO()
    doc = SimpleDocTemplate(
        bio, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm,
        topMargin=36*mm, bottomMargin=18*mm
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title2", parent=styles["Heading1"], fontName="Helvetica-Bold",
                           fontSize=16, leading=19, textColor=colors.HexColor("#161616"), spaceAfter=10)
    body = ParagraphStyle("body2", parent=styles["BodyText"], fontSize=9.5, leading=13)
    orange = colors.HexColor("#ff6a00")

    c = q["calculo"]
    story = [Paragraph("COTACAO DE TRANSPORTE", title)]
    story.append(Paragraph(f"Cotacao <b>{q['numero']}</b> - Emitida em {q['data']}", body))
    story.append(Spacer(1, 6*mm))

    dados = [
        ["Cliente", q.get("cliente") or "-"],
        ["CNPJ", q.get("cnpj") or "-"],
        ["Contato", q.get("contato") or "-"],
        ["Origem", f"{q.get('cep_origem','-')} {q.get('cidade_origem','')}".strip()],
        ["Destino", f"{q.get('cep_destino','-')} {q.get('cidade_destino','')}".strip()],
        ["Veiculo", q.get("veiculo") or "-"],
        ["Distancia considerada", f"{fmt(c.get('km_total',0))} km"],
        ["Pedagio", "Incluso" if c.get("pedagio_total",0) > 0 else "Nao informado / nao incluso"],
        ["Validade", f"{q.get('validade_dias',7)} dias"],
    ]
    t = Table(dados, colWidths=[48*mm, 120*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f2f2f2")),
        ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#333333")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#dddddd")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story += [t, Spacer(1, 8*mm)]

    valor = Table([["VALOR DO TRANSPORTE", brl(c.get("preco_final",0))]], colWidths=[90*mm, 78*mm])
    valor.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#151515")),
        ("TEXTCOLOR", (0,0), (0,0), colors.white),
        ("TEXTCOLOR", (1,0), (1,0), orange),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (0,0), 11),
        ("FONTSIZE", (1,0), (1,0), 16),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    story += [valor]

    if q.get("observacoes"):
        story += [Spacer(1, 7*mm), Paragraph("<b>Observacoes</b>", body), Paragraph(q["observacoes"], body)]

    story += [Spacer(1, 11*mm), Paragraph(
        "Esta cotacao apresenta somente as condicoes comerciais da operacao. A memoria interna de custos nao integra este documento.", body
    )]
    doc.build(story, onFirstPage=lambda c, d: _pdf_header(c, d, "Relatorio para cliente"),
              onLaterPages=lambda c, d: _pdf_header(c, d, "Relatorio para cliente"))
    bio.seek(0)
    return bio.getvalue()


def gerar_pdf_interno(q):
    if not REPORTLAB_OK:
        return None
    bio = BytesIO()
    doc = SimpleDocTemplate(
        bio, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
        topMargin=36*mm, bottomMargin=16*mm
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ititle", parent=styles["Heading1"], fontName="Helvetica-Bold",
                           fontSize=15, leading=18, textColor=colors.HexColor("#161616"), spaceAfter=8)
    body = ParagraphStyle("ibody", parent=styles["BodyText"], fontSize=8.8, leading=12)
    c = q["calculo"]
    p = q.get("parametros_usados", {})
    story = [Paragraph("FECHAMENTO INTERNO DA COTACAO", title)]
    story += [Paragraph(f"Cotacao <b>{q['numero']}</b> - {q['data']} - Status: <b>{q.get('status','-')}</b>", body), Spacer(1,5*mm)]

    resumo = [
        ["Cliente", q.get("cliente") or "-", "Veiculo", q.get("veiculo") or "-"],
        ["Origem", q.get("cep_origem") or "-", "Destino", q.get("cep_destino") or "-"],
        ["KM ida", f"{fmt(q.get('km_ida',0))} km", "KM volta", f"{fmt(q.get('km_volta_considerado',0))} km"],
        ["KM total", f"{fmt(c.get('km_total',0))} km", "Pedagio total", brl(c.get("pedagio_total",0))],
    ]
    rt = Table(resumo, colWidths=[29*mm, 58*mm, 29*mm, 58*mm])
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f2f2f2")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#f2f2f2")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#dcdcdc")),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story += [rt, Spacer(1,6*mm)]

    custos = [
        ["Componente", "Base / quantidade", "Valor"],
        ["Diesel", f"{fmt(c.get('diesel_litros',0))} L x {brl(p.get('diesel_litro',0))}/L", brl(c.get("custo_diesel",0))],
        ["ARLA 32", f"{fmt(c.get('arla_litros',0))} L x {brl(p.get('arla_litro',0))}/L", brl(c.get("custo_arla",0))],
        ["Manutencao / lubrificantes", f"{fmt(c.get('km_total',0))} km x {brl(p.get('manutencao_km',0))}/km", brl(c.get("custo_manutencao",0))],
        ["Pneus", f"{fmt(c.get('km_total',0))} km x {brl(p.get('pneus_km',0))}/km", brl(c.get("custo_pneus",0))],
        ["Outros variaveis", "Por viagem", brl(c.get("outros_variaveis",0))],
        ["Pedagios", "Ida + volta considerados", brl(c.get("pedagio_total",0))],
        ["Horas paradas", f"{fmt(q.get('horas_paradas',0))} h", brl(c.get("custo_horas_paradas",0))],
    ]
    for nome, valor in c.get("fixos", {}).items():
        custos.append([nome, "Rateio por viagem", brl(valor)])
    custos += [
        ["Adicional fixo", q.get("adicional_descricao") or "Adicional", brl(c.get("adicional_valor",0))],
        ["Adicional percentual", f"{fmt(c.get('adicional_percentual',0))}%", brl(c.get("adicional_pct_valor",0))],
        ["CUSTO OPERACIONAL", "", brl(c.get("custo_operacional",0))],
        ["Markup", f"{fmt(c.get('markup_percentual',0))}%", brl(c.get("markup_valor",0))],
        ["Impostos", f"{fmt(c.get('impostos_percentual',0))}%", brl(c.get("imposto_valor",0))],
        ["PRECO FINAL", f"{brl(c.get('valor_km',0))}/km", brl(c.get("preco_final",0))],
    ]
    ct = Table(custos, colWidths=[63*mm, 73*mm, 42*mm], repeatRows=1)
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#151515")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 7.7),
        ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9d9d9")),
        ("ALIGN", (2,1), (2,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("BACKGROUND", (0,-3), (-1,-3), colors.HexColor("#f3f3f3")),
        ("FONTNAME", (0,-3), (-1,-3), "Helvetica-Bold"),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#fff0e5")),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2,-1), (2,-1), colors.HexColor("#e65f00")),
    ]))
    story += [ct]
    if q.get("observacoes"):
        story += [Spacer(1,6*mm), Paragraph("<b>Observacoes:</b> " + q["observacoes"], body)]

    doc.build(story, onFirstPage=lambda c, d: _pdf_header(c, d, "Fechamento interno"),
              onLaterPages=lambda c, d: _pdf_header(c, d, "Fechamento interno"))
    bio.seek(0)
    return bio.getvalue()


# =========================================================
# LOGIN
# =========================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">GDS <span>ROTAS</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Precificacao operacional e comercial</div>', unsafe_allow_html=True)
    senha = st.text_input("Senha de acesso", type="password", placeholder="Digite sua senha")
    if st.button("Entrar", type="primary", use_container_width=True):
        if senha == APP_PASSWORD:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# =========================================================
# NAVEGAÇÃO
# =========================================================
if "pagina" not in st.session_state:
    st.session_state.pagina = "Início"

with st.sidebar:
    st.markdown('<div class="brand">GDS <span>ROTAS</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-sub">Precificação de transporte</div>', unsafe_allow_html=True)
    st.caption("☁️ Dados no GitHub" if USE_GITHUB_DB else "💻 Dados locais")
    if st.button("🏠  Início", use_container_width=True): st.session_state.pagina = "Início"
    if st.button("🧮  Nova cotação", use_container_width=True): st.session_state.pagina = "Nova cotação"
    if st.button("🕘  Histórico", use_container_width=True): st.session_state.pagina = "Histórico"
    if st.button("📄  Relatórios", use_container_width=True): st.session_state.pagina = "Relatórios"
    if st.button("⚙️  Parâmetros", use_container_width=True): st.session_state.pagina = "Parâmetros"
    st.markdown("---")
    if st.button("Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

pagina = st.session_state.pagina
params = carregar_parametros()
historico = carregar_historico()


def hero(titulo, subtitulo):
    st.markdown(f'<div class="hero"><h1>{titulo}</h1><p>{subtitulo}</p></div>', unsafe_allow_html=True)


# =========================================================
# INÍCIO
# =========================================================
if pagina == "Início":
    hero("Precificação de Rotas", "Controle de custos, cotações e memória de cálculo em um único lugar.")
    cols = st.columns(4)
    cards = [
        ("🧮", "Nova cotação", "Monte uma rota manualmente com KM e pedágio."),
        ("🕘", "Histórico", "Consulte todas as cotações salvas."),
        ("📄", "Relatórios", "Gere versão comercial ou fechamento interno."),
        ("⚙️", "Parâmetros", "Ajuste diesel, ARLA, custos e markup."),
    ]
    for col, (ico, tit, desc) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="menu-card"><div class="icon">{ico}</div><div class="title">{tit}</div><div class="desc">{desc}</div></div>', unsafe_allow_html=True)

    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Diesel", brl(params["diesel_litro"]) + "/L")
    c2.metric("ARLA 32", brl(params["arla_litro"]) + "/L")
    c3.metric("Markup padrão", f"{fmt(params['markup_percentual'])}%")
    c4.metric("Cotações salvas", len(historico))

    if historico:
        st.markdown("### Últimas cotações")
        for q in sorted(historico, key=lambda x: x.get("criado_em", ""), reverse=True)[:5]:
            st.markdown(
                f'<div class="quote-row"><div class="qtitle">{q.get("numero","-")} · {q.get("cliente") or "Cliente não informado"}</div>'
                f'<div class="qmeta">{q.get("cep_origem","-")} → {q.get("cep_destino","-")} · {fmt(q.get("calculo",{}).get("km_total",0))} km · {brl(q.get("calculo",{}).get("preco_final",0))} · {q.get("status","-")}</div></div>',
                unsafe_allow_html=True
            )


# =========================================================
# NOVA COTAÇÃO
# =========================================================
elif pagina == "Nova cotação":
    hero("Nova Cotação", "Informe CEP, quilometragem e pedágio. O cálculo financeiro é feito automaticamente.")

    with st.form("form_cotacao", clear_on_submit=False):
        st.markdown("### 1. Cliente e operação")
        a,b,c = st.columns(3)
        cliente = a.text_input("Cliente / Razão Social")
        cnpj = b.text_input("CNPJ")
        contato = c.text_input("Contato")
        a,b,c = st.columns(3)
        veiculo = a.selectbox("Tipo de veículo", VEICULOS)
        cidade_origem = b.text_input("Cidade/UF origem (opcional)")
        cidade_destino = c.text_input("Cidade/UF destino (opcional)")

        st.markdown("### 2. Rota")
        a,b = st.columns(2)
        cep_origem = a.text_input("CEP origem", placeholder="00000-000")
        cep_destino = b.text_input("CEP destino", placeholder="00000-000")

        a,b,c = st.columns([1,1,1.15])
        km_ida = a.number_input("KM ida", min_value=0.0, step=1.0, format="%.1f")
        usar_volta_km = b.checkbox("Considerar KM de volta", value=True)
        km_volta = c.number_input("KM volta", min_value=0.0, value=float(km_ida), step=1.0, format="%.1f",
                                  disabled=not usar_volta_km)

        a,b,c = st.columns([1,1,1.15])
        pedagio_ida = a.number_input("Pedágio ida (R$)", min_value=0.0, step=1.0, format="%.2f")
        usar_volta_pedagio = b.checkbox("Considerar pedágio da volta", value=True)
        pedagio_volta = c.number_input("Pedágio volta (R$)", min_value=0.0, value=float(pedagio_ida), step=1.0, format="%.2f",
                                       disabled=not usar_volta_pedagio)

        st.markdown("### 3. Adicionais")
        a,b,c = st.columns([2,1,1])
        adicional_descricao = a.text_input("Descrição do adicional", placeholder="Ex.: ajudante, diária, pernoite...")
        adicional_valor = b.number_input("Adicional fixo (R$)", min_value=0.0, step=10.0, format="%.2f")
        adicional_percentual = c.number_input("Adicional (%)", min_value=0.0, step=0.5, format="%.2f")
        horas_paradas = st.number_input("Horas paradas cobradas", min_value=0.0, step=0.5, format="%.1f")
        observacoes = st.text_area("Observações da cotação")

        calcular = st.form_submit_button("Calcular cotação", type="primary", use_container_width=True)

    if calcular:
        if km_ida <= 0:
            st.error("Informe a quilometragem de ida para calcular.")
        else:
            # se a volta estiver marcada e o usuário deixou 0, assume o mesmo KM/pedágio da ida
            km_volta_real = km_volta if km_volta > 0 else km_ida
            pedagio_volta_real = pedagio_volta if pedagio_volta > 0 else pedagio_ida
            calc = calcular_cotacao(
                params, km_ida, usar_volta_km, km_volta_real,
                pedagio_ida, usar_volta_pedagio, pedagio_volta_real,
                adicional_valor, adicional_percentual, horas_paradas
            )
            st.session_state["cotacao_em_calculo"] = {
                "numero": proximo_numero(historico),
                "data": datetime.now().strftime("%d/%m/%Y"),
                "criado_em": datetime.now().isoformat(timespec="seconds"),
                "status": "Em análise",
                "cliente": cliente.strip(), "cnpj": cnpj.strip(), "contato": contato.strip(),
                "veiculo": veiculo,
                "cidade_origem": cidade_origem.strip(), "cidade_destino": cidade_destino.strip(),
                "cep_origem": normalizar_cep(cep_origem), "cep_destino": normalizar_cep(cep_destino),
                "km_ida": km_ida,
                "usar_volta_km": usar_volta_km,
                "km_volta_considerado": km_volta_real if usar_volta_km else 0.0,
                "pedagio_ida": pedagio_ida,
                "usar_volta_pedagio": usar_volta_pedagio,
                "pedagio_volta_considerado": pedagio_volta_real if usar_volta_pedagio else 0.0,
                "adicional_descricao": adicional_descricao.strip(),
                "horas_paradas": horas_paradas,
                "observacoes": observacoes.strip(),
                "validade_dias": int(params.get("validade_cotacao_dias",7)),
                "parametros_usados": dict(params),
                "calculo": calc,
            }

    q = st.session_state.get("cotacao_em_calculo")
    if q:
        c = q["calculo"]
        st.markdown("### Resultado da cotação")
        a,b,c1,d = st.columns(4)
        a.markdown(f'<div class="kpi"><div class="label">KM total</div><div class="value">{fmt(c["km_total"])} km</div><div class="sub">ida + volta considerada</div></div>', unsafe_allow_html=True)
        b.markdown(f'<div class="kpi"><div class="label">Custo operacional</div><div class="value">{brl(c["custo_operacional"])}</div><div class="sub">antes do markup</div></div>', unsafe_allow_html=True)
        c1.markdown(f'<div class="kpi"><div class="label">Preço sugerido</div><div class="value">{brl(c["preco_final"])}</div><div class="sub">markup {fmt(c["markup_percentual"])}%</div></div>', unsafe_allow_html=True)
        d.markdown(f'<div class="kpi"><div class="label">Preço por KM</div><div class="value">{brl(c["valor_km"])}</div><div class="sub">valor final / km total</div></div>', unsafe_allow_html=True)

        with st.expander("Ver memória de cálculo", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"Diesel: **{fmt(c['diesel_litros'])} L** → **{brl(c['custo_diesel'])}**")
                st.write(f"ARLA 32: **{fmt(c['arla_litros'])} L** → **{brl(c['custo_arla'])}**")
                st.write(f"Manutenção: **{brl(c['custo_manutencao'])}**")
                st.write(f"Pneus: **{brl(c['custo_pneus'])}**")
                st.write(f"Pedágio total: **{brl(c['pedagio_total'])}**")
            with col2:
                st.write(f"Custos fixos: **{brl(c['total_fixos'])}**")
                st.write(f"Outros variáveis: **{brl(c['outros_variaveis'])}**")
                st.write(f"Adicionais: **{brl(c['adicional_valor'] + c['adicional_pct_valor'])}**")
                st.write(f"Markup: **{brl(c['markup_valor'])}**")
                st.write(f"Preço final: **{brl(c['preco_final'])}**")

        a,b = st.columns(2)
        if a.button("💾 Salvar cotação", type="primary", use_container_width=True):
            # evita duplicar a mesma cotação já salva
            existente = next((i for i,x in enumerate(historico) if x.get("numero") == q.get("numero")), None)
            if existente is None:
                historico.append(q)
            else:
                historico[existente] = q
            try:
                salvar_historico(historico)
                st.success(f"Cotação {q['numero']} salva com sucesso.")
            except Exception as e:
                st.error(f"Não foi possível salvar a cotação: {e}")
        if b.button("Limpar cálculo", use_container_width=True):
            st.session_state.pop("cotacao_em_calculo", None)
            st.rerun()


# =========================================================
# HISTÓRICO
# =========================================================
elif pagina == "Histórico":
    hero("Histórico de Cotações", "Consulte valores, altere status e recupere relatórios das cotações já salvas.")
    if not historico:
        st.info("Nenhuma cotação salva ainda.")
    else:
        a,b,c = st.columns([2,1,1])
        busca = a.text_input("Buscar por nº, cliente, CEP ou destino")
        filtro_status = b.selectbox("Status", ["Todos"] + STATUS_COTACAO)
        ordem = c.selectbox("Ordenação", ["Mais recentes", "Mais antigas", "Maior valor", "Menor valor"])

        dados = historico[:]
        if busca.strip():
            termo = busca.lower().strip()
            dados = [q for q in dados if termo in " ".join([
                str(q.get("numero","")), str(q.get("cliente","")), str(q.get("cep_origem","")),
                str(q.get("cep_destino","")), str(q.get("cidade_destino",""))
            ]).lower()]
        if filtro_status != "Todos":
            dados = [q for q in dados if q.get("status") == filtro_status]
        if ordem == "Mais recentes": dados.sort(key=lambda x:x.get("criado_em",""), reverse=True)
        elif ordem == "Mais antigas": dados.sort(key=lambda x:x.get("criado_em",""))
        elif ordem == "Maior valor": dados.sort(key=lambda x:x.get("calculo",{}).get("preco_final",0), reverse=True)
        else: dados.sort(key=lambda x:x.get("calculo",{}).get("preco_final",0))

        for q in dados:
            c = q.get("calculo",{})
            with st.expander(f"{q.get('numero','-')} · {q.get('cliente') or 'Cliente não informado'} · {brl(c.get('preco_final',0))}"):
                st.write(f"**Rota:** {q.get('cep_origem','-')} → {q.get('cep_destino','-')}  |  **KM:** {fmt(c.get('km_total',0))}  |  **Veículo:** {q.get('veiculo','-')}")
                cols = st.columns([1.5,1,1,1])
                novo_status = cols[0].selectbox("Status", STATUS_COTACAO, index=STATUS_COTACAO.index(q.get("status","Em análise")) if q.get("status") in STATUS_COTACAO else 0, key=f"status_{q['numero']}")
                if cols[1].button("Salvar status", key=f"save_{q['numero']}", use_container_width=True):
                    for item in historico:
                        if item.get("numero") == q.get("numero"):
                            item["status"] = novo_status
                            break
                    try:
                        salvar_historico(historico)
                        st.success("Status atualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar: {e}")
                if cols[2].button("Duplicar", key=f"dup_{q['numero']}", use_container_width=True):
                    novo = dict(q)
                    novo["numero"] = proximo_numero(historico)
                    novo["data"] = datetime.now().strftime("%d/%m/%Y")
                    novo["criado_em"] = datetime.now().isoformat(timespec="seconds")
                    novo["status"] = "Em análise"
                    historico.append(novo)
                    try:
                        salvar_historico(historico)
                        st.success(f"Duplicada como {novo['numero']}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível duplicar: {e}")
                if cols[3].button("Excluir", key=f"del_{q['numero']}", use_container_width=True):
                    historico = [x for x in historico if x.get("numero") != q.get("numero")]
                    try:
                        salvar_historico(historico)
                        st.success("Cotação excluída.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível excluir: {e}")


# =========================================================
# RELATÓRIOS
# =========================================================
elif pagina == "Relatórios":
    hero("Relatórios", "Gere uma versão comercial para o cliente ou o fechamento completo para uso interno.")
    if not historico:
        st.info("Salve pelo menos uma cotação para gerar relatórios.")
    else:
        opcoes = {f"{q.get('numero')} · {q.get('cliente') or 'Sem cliente'} · {brl(q.get('calculo',{}).get('preco_final',0))}": q for q in sorted(historico, key=lambda x:x.get("criado_em",""), reverse=True)}
        escolhido = st.selectbox("Selecione a cotação", list(opcoes.keys()))
        q = opcoes[escolhido]
        st.write(f"**Rota:** {q.get('cep_origem','-')} → {q.get('cep_destino','-')} | **Valor final:** {brl(q.get('calculo',{}).get('preco_final',0))}")

        if not REPORTLAB_OK:
            st.warning("Para gerar PDF no PC, instale o ReportLab: `py -m pip install reportlab`")
        else:
            col1, col2 = st.columns(2)
            pdf_cliente = gerar_pdf_cliente(q)
            pdf_interno = gerar_pdf_interno(q)
            with col1:
                st.markdown("### 📄 Relatório para cliente")
                st.caption("Sem detalhamento de diesel, ARLA, custos fixos ou markup.")
                st.download_button(
                    "Baixar PDF para cliente",
                    data=pdf_cliente,
                    file_name=f"{q['numero']}_cliente.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
            with col2:
                st.markdown("### 🔒 Fechamento interno")
                st.caption("Memória completa de custos, adicionais, markup e valor final.")
                st.download_button(
                    "Baixar PDF de fechamento",
                    data=pdf_interno,
                    file_name=f"{q['numero']}_fechamento.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )


# =========================================================
# PARÂMETROS
# =========================================================
elif pagina == "Parâmetros":
    hero("Parâmetros de Precificação", "Altere os valores-base sem precisar editar o código do aplicativo.")
    with st.form("param_form"):
        st.markdown("### Combustível e consumo")
        a,b,c,d = st.columns(4)
        diesel = a.number_input("Diesel (R$/L)", min_value=0.0, value=float(params["diesel_litro"]), step=0.01, format="%.2f")
        consumo = b.number_input("Consumo médio (km/L)", min_value=0.1, value=float(params["consumo_km_l"]), step=0.1, format="%.2f")
        arla = c.number_input("ARLA 32 (R$/L)", min_value=0.0, value=float(params["arla_litro"]), step=0.01, format="%.2f")
        razao = d.number_input("Litros diesel para 1 L de ARLA", min_value=1.0, value=float(params["diesel_por_litro_arla"]), step=1.0)

        st.markdown("### Custos por KM e por viagem")
        a,b,c = st.columns(3)
        manut = a.number_input("Manutenção/lubrificantes (R$/km)", min_value=0.0, value=float(params["manutencao_km"]), step=0.01, format="%.2f")
        pneus = b.number_input("Pneus (R$/km)", min_value=0.0, value=float(params["pneus_km"]), step=0.01, format="%.2f")
        outrosvar = c.number_input("Outros variáveis / viagem (R$)", min_value=0.0, value=float(params["outros_variaveis_viagem"]), step=10.0, format="%.2f")

        st.markdown("### Custos fixos rateados por viagem")
        a,b,c = st.columns(3)
        depreciacao = a.number_input("Depreciação", min_value=0.0, value=float(params["depreciacao_viagem"]), step=10.0, format="%.2f")
        salario = b.number_input("Salário motorista", min_value=0.0, value=float(params["salario_motorista_viagem"]), step=10.0, format="%.2f")
        encargos = c.number_input("Encargos motorista", min_value=0.0, value=float(params["encargos_motorista_viagem"]), step=10.0, format="%.2f")
        a,b,c = st.columns(3)
        seguro = a.number_input("Seguro veículo", min_value=0.0, value=float(params["seguro_viagem"]), step=10.0, format="%.2f")
        adm = b.number_input("Despesas administrativas", min_value=0.0, value=float(params["despesas_adm_viagem"]), step=10.0, format="%.2f")
        outrasfixas = c.number_input("Outras despesas fixas", min_value=0.0, value=float(params["outras_fixas_viagem"]), step=10.0, format="%.2f")

        st.markdown("### Comercial")
        a,b,c,d = st.columns(4)
        markup = a.number_input("Markup padrão (%)", min_value=0.0, value=float(params["markup_percentual"]), step=1.0, format="%.2f")
        imposto = b.number_input("Impostos (%)", min_value=0.0, value=float(params.get("impostos_percentual",0)), step=0.5, format="%.2f")
        frete_min = c.number_input("Frete mínimo (R$)", min_value=0.0, value=float(params.get("frete_minimo",0)), step=10.0, format="%.2f")
        hora_parada = d.number_input("Hora parada (R$/h)", min_value=0.0, value=float(params.get("hora_parada",0)), step=10.0, format="%.2f")
        validade = st.number_input("Validade padrão da cotação (dias)", min_value=1, value=int(params.get("validade_cotacao_dias",7)), step=1)

        salvar = st.form_submit_button("Salvar parâmetros", type="primary", use_container_width=True)
    if salvar:
        novo = {
            "diesel_litro": diesel, "consumo_km_l": consumo, "arla_litro": arla,
            "diesel_por_litro_arla": razao, "manutencao_km": manut, "pneus_km": pneus,
            "outros_variaveis_viagem": outrosvar, "depreciacao_viagem": depreciacao,
            "salario_motorista_viagem": salario, "encargos_motorista_viagem": encargos,
            "seguro_viagem": seguro, "despesas_adm_viagem": adm, "outras_fixas_viagem": outrasfixas,
            "markup_percentual": markup, "impostos_percentual": imposto,
            "frete_minimo": frete_min, "hora_parada": hora_parada,
            "validade_cotacao_dias": int(validade),
        }
        try:
            salvar_parametros(novo)
            st.success("Parâmetros salvos com sucesso.")
            st.rerun()
        except Exception as e:
            st.error(f"Não foi possível salvar os parâmetros: {e}")
