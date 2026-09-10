import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests  # (ou a biblioteca que você usa para chamar a API da Stays)
from datetime import datetime

# ==========================================
# BLOCO 1: SEU CÓDIGO DA STAYS.NET (EXEMPLO)
# ==========================================
import requests
import base64
import json
import pandas as pd
from datetime import datetime, timedelta

# 1. Configurações de Acesso
base_url = "https://www.booksantos.com.br"
username = "09af95bc"
password = "3c4699d1"

credentials = f"{username}:{password}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

headers = {
    "Authorization": f"Basic {encoded_credentials}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# 2. Janela Dinâmica Inteligente (60 dias para trás e 60 dias para frente)
hoje = datetime.now().date()
data_inicio = hoje - timedelta(days=60)
data_fim = hoje + timedelta(days=60)

endpoint = f"{base_url}/external/v1/booking/reservations-export"
payload = {
    "from": data_inicio.strftime("%Y-%m-%d"),
    "to": data_fim.strftime("%Y-%m-%d"),
    "dateType": "arrival"
}

print(f"Buscando reservas de {payload['from']} até {payload['to']}...")
response = requests.post(endpoint, headers=headers, json=payload)

if response.status_code == 200:
    reservas = response.json()
    print(f"Sucesso! {len(reservas)} reservas encontradas. Processando...")
    
    lista_processada = []
    
    for r in reservas:
        check_in = r.get("checkInDate")
        check_out = r.get("checkOutDate")
        hospedes = r.get("guestTotalCount", 1)
        
        # Dados do imóvel (Unidade)
        listing = r.get("listing", {})
        nome_unidade = listing.get("internalName", "Não informado")
        
        # Regra de Cálculo de Enxoval por Hóspede
        travesseiros = hospedes * 2
        fronhas = hospedes * 2
        lençóis = hospedes * 1
        cobertores = hospedes * 1
        toalhas_rosto = hospedes * 1
        toalhas_banho = hospedes * 1
        
        lista_processada.append({
            "Check-in": check_in,
            "Check-out": check_out,
            "Unidade / Apto": nome_unidade,
            "Hóspedes": hospedes,
            "Travesseiros": travesseiros,
            "Fronhas": fronhas,
            "Jogos de Lençóis": lençóis,
            "Cobertores": cobertores,
            "Panos de Prato": 2,
            "Toalhas de Rosto": toalhas_rosto,
            "Toalhas de Banho": toalhas_banho
        })
    
           # Criando o DataFrame e ordenando cronologicamente
        df = pd.DataFrame(lista_processada)
    if not df.empty:
        # Converte as colunas de data para texto puro no formato YYYY-MM-DD
        df["Check-in"] = pd.to_datetime(df["Check-in"]).dt.strftime('%Y-%m-%d')
        df["Check-out"] = pd.to_datetime(df["Check-out"]).dt.strftime('%Y-%m-%d')
        
        df = df.sort_values(by="Check-in", ascending=True)
        
        print("Dados processados com sucesso. Enviando para o Google Drive...")
    else:
        print(f"Erro ao buscar reservas: {response.status_code} - {response.text}")

    # Salvando em Excel
    # nome_arquivo = "Agenda_Studio_Clean_Final.xlsx"
    # df.to_excel(nome_arquivo, index=False)
    # print("Dados processados com sucesso. Enviando para o Google Drive")
    
    # Mostra uma prévia na tela
    
# ==========================================
# BLOCO 2: CONEXÃO COM O GOOGLE DRIVE (GSPREAD)
# ==========================================
import os
import base64
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64")

if creds_b64:
    creds_b64_clean = creds_b64.strip().encode("ascii", "ignore")
    json_bytes = base64.b64decode(creds_b64_clean)
    creds_dict = json.loads(json_bytes.decode("utf-8", errors="ignore"))
    
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    raise ValueError("O Secret GOOGLE_CREDENTIALS_B64 não foi configurado no GitHub Actions!")

client = gspread.authorize(creds)

# ==========================================
# BLOCO 3: ATUALIZAÇÃO DA PLANILHA NA NUVEM
# ==========================================
spreadsheet_name = "Agenda_Studio_Clean"
sheet = client.open(spreadsheet_name).worksheet("Sheet1")

# Limpa os dados antigos da aba
sheet.clear()

# Prepara os dados (cabeçalho + linhas) vindos do Stays e atualiza a planilha
data_to_upload = [df.columns.tolist()] + df.values.tolist()
sheet.update("A1", data_to_upload)

print("Dados do Stays puxados e planilha atualizada com sucesso na nuvem!")

import os
import smtplib
from email.message import EmailMessage

def enviar_email_atualizacao(link_planilha, destinatario):
    # Puxa as credenciais de forma segura das variaveis de ambiente do GitHub
    EMAIL_ORIGEM = os.environ.get("MEU_EMAIL")
    SENHA_APLICATIVO = os.environ.get("SENHA_APP")
    
    msg = EmailMessage()
    msg['Subject'] = 'Agenda Studio Clean Atualizada'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = "atendimentostudioclean@gmail.com"
    
    conteudo = f"""
    Olá!
    
    A agenda de reservas do Studio Clean foi atualizada com sucesso no horário programado.
    Você pode acessar os dados mais recentes através do link abaixo:
    
    {link_planilha}
    
    Atenciosamente,
    Automação Studio Clean
    """
    
    msg.set_content(conteudo)
    
    try:
        # Conectando ao servidor SMTP do Gmail (ou outro provedor)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ORIGEM, SENHA_APLICATIVO)
            smtp.send_message(msg)
        print("E-mail de notificação enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar o e-mail: {e}")

# Chame a função passando o link da sua planilha e o e-mail do cliente:
# Chame a função passando o link da sua planilha e o e-mail do cliente:
enviar_email_atualizacao("https://docs.google.com/spreadsheets/d/15eNX1NkBrUG3AhEaiaoFw39h_z4Pj-0ulqGk6vJgpVQ/edit?usp=drive_link", "atendimentostudioclean@gmail.com")
