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
        df = df.sort_values(by="Check-in", ascending=True)
    
    # Salvando em Excel
    nome_arquivo = "Agenda_Studio_Clean_Final.xlsx"
    df.to_excel(nome_arquivo, index=False)
    print(f"Pronto! Planilha gerada com sucesso: '{nome_arquivo}'")
    
    # Mostra uma prévia na tela
    
else:
    print(f"Erro ao buscar reservas: {response.status_code} - {response.text}")

# ==========================================
# BLOCO 2: CONEXÃO COM O GOOGLE DRIVE (GSPREAD)
# ==========================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Nome exato do arquivo JSON que está na sua pasta (e que você vai subir no GitHub junto com este script)
CREDENTIALS_FILE = "sudiocleanautomation-cb99c084c8f8.json"

creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
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
