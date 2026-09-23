import os
import requests
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# 1. Configurações de Acesso
KOBO_URL = "https://kf.kobotoolbox.org"
ASSET_UID = "aoXMqam2RfsKFvZVPkQdn6"
TOKEN = "a21c8e2faa2199f313a9bbdc231f405078fbf2b6"

HEADERS = {
    "Authorization": f"Token {TOKEN}"
}

CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MAPA_PRESTADORAS = {
    "i_01": "Carla dos Santos São José",
    "i_02": "Milena Carvalho Dos Santos",
    "i_03": "Milene Carvalho Dos Santos",
    "s_04": "Andreza Fonik Silvia De Lima",
    "c_05": "Maria Helena Da Silva Santos",
    "c_06": "Maria Cicera Silva Mascarenhas",
    "c_07": "Natalia Nascimento De Carvalho",
    "c_08": "Nicole Gabriele Hohman De Oliveira",
    "c_09": "Kaylane Lourdes Santos Coelho",
    "c_10": "Patricia Maria Da Silva Mascarenhas",
    "c_11": "Thayna Ferreira Dos Santos",
    "c_12": "Iris Beatriz Correa Alves",
    "c_13": "Renata Rodrigues Dos Santos",
    "c_14": "Yasmin Correa Alves",
    "c_15": "Graziele Feitosa de Souza",
    "c_16": "Rosangela Ferreira Rodrigues"
}

def extrair_dados_kobo():
    url = f"{KOBO_URL}/api/v2/assets/{ASSET_UID}/data/"
    print("Conectando ao KoboToolbox para extrair as vistorias...")
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        dados = response.json().get("results", [])
        print(f"Sucesso! {len(dados)} registros encontrados no Kobo.")
        return dados
    else:
        print(f"Erro ao acessar a API: {response.status_code} - {response.text}")
        return None

def calcular_duracao(inicio_str, fim_str):
    try:
        fmt = "%H:%M:%S"
        t1 = datetime.strptime(inicio_str.split(".")[0][:8], fmt)
        t2 = datetime.strptime(fim_str.split(".")[0][:8], fmt)
        diff = t2 - t1
        segundos = int(diff.total_seconds())
        if segundos < 0:
            return "Não calculado"
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        if horas > 0:
            return f"{horas}h {minutos}min"
        else:
            return f"{minutos} min"
    except Exception:
        return "Não informado"

def processar_registros(dados):
    lista_processada = []

    for reg in dados:
        condominio = reg.get("grp_ident/cond_nome", "")
        endereco = reg.get("grp_ident/endereco_cond", "")
        apartamento = reg.get("grp_ident/apto", "")
        
        codigo_prestadora = reg.get("grp_ident/prestadora", "")
        prestadora = MAPA_PRESTADORAS.get(codigo_prestadora, codigo_prestadora)
        
        tipo_apto = reg.get("tipo_apto", "")
        tem_jacuzzi = reg.get("tem_jacuzzi", "")
        n_quartos = reg.get("n_quartos", "")
        n_banheiros = reg.get("n_banheiros", "")
        tipo_servico = reg.get("tipo_servico", "")
        
        data_servico = reg.get("grp_localhora/data_servico", "")
        hora_inicio = reg.get("grp_localhora/hora_inicio", "")
        hora_fim = reg.get("hora_fim", "")
        tempo_trabalho = calcular_duracao(hora_inicio, hora_fim)
        enviar_por = reg.get("_submitted_by", "")

        total_itens = 0
        itens_ok = 0
        for chave, valor in reg.items():
            if any(termo in chave.lower() for termo in ["verificar", "lavar", "limpar", "abastecer", "conferir", "repor", "bater", "tirar", "guardar", "colocar", "trancar", "jacuzzi"]):
                total_itens += 1
                if valor in ["yes", "ok", "1", True]:
                    itens_ok += 1
        
        percentual_conclusao = round((itens_ok / total_itens * 100), 1) if total_itens > 0 else 0.0

        obs_vistoria = reg.get("grp_vistoria/vis_ocorrencias", "")
        obs_geral = reg.get("Vistoria / Ocorrências / Observações", "")
        ocorrencias_finais = f"{obs_vistoria} {obs_geral}".strip()

        linha = {
            "Data": data_servico,
            "Condomínio": condominio,
            "Endereço": endereco,
            "Apartamento": apartamento,
            "Prestadora": prestadora,
            "Tipo Apto": tipo_apto,
            "Quartos": n_quartos,
            "Banheiros": n_banheiros,
            "Jacuzzi": tem_jacuzzi,
            "Serviço": tipo_servico,
            "Início": hora_inicio,
            "Término": hora_fim,
            "Tempo de Trabalho": tempo_trabalho,
            "Conclusão (%)": f"{percentual_conclusao}%",
            "Ocorrências / Obs": ocorrencias_finais,
            "Enviado por": enviar_por
        }
        lista_processada.append(linha)

    return pd.DataFrame(lista_processada)

def criar_historico_google_sheets(df):
    if df.empty:
        print("Nenhum dado para enviar.")
        return

    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nome_arquivo_semanal = f"Checklist_Kobo_Historico_{data_atual}"
    
    # IDs protegidos e direcionados
    TEMPLATE_ID = "1qxtMHo9_h1T1-2C6BdMKxmarQbH33ikPyCOKHhYawRc"
    PASTA_DESTINO_ID = "1_fw1PjAjsSnZ_yLE6IHm4DRHYlDk7kmu"
    
    try:
        # Abre o template protegido diretamente pelo ID
        template_spreadsheet = client.open_by_key(TEMPLATE_ID)
        
        # Copia o template gerando um novo arquivo exclusivo direto na pasta de histórico
        novo_arquivo = client.copy(template_spreadsheet.id, title=nome_arquivo_semanal, folder_id=PASTA_DESTINO_ID)
        
        sheet = novo_arquivo.sheet1
        sheet.clear()
        
        print(f"Histórico semanal criado com sucesso na pasta de destino: '{nome_arquivo_semanal}'")
    except Exception as e:
        print(f"Erro detalhado ao processar no Google Drive: {e}")
        return

    data_to_upload = [df.columns.tolist()] + df.values.tolist()
    sheet.update("A1", data_to_upload)
    print("Sucesso absoluto! Dados atualizados no novo arquivo.")

if __name__ == "__main__":
    dados_brutos = extrair_dados_kobo()
    if dados_brutos:
        df_final = processar_registros(dados_brutos)
        criar_historico_google_sheets(df_final)
