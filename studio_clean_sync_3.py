import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests  # (ou a biblioteca que você usa para chamar a API da Stays)
from datetime import datetime

# ==========================================
# BLOCO 1: SEU CÓDIGO DA STAYS.NET (COM FILTRO DO GRUPO E RETRY)
# ==========================================
import requests
import base64
import json
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. Configurações de Acesso Gerais e de Conteúdo
base_url = "https://www.booksantos.com.br"

# Credenciais de Conteúdo para buscar grupos e listagens
user_content = "49831679"
pass_content = "23cf07f4"
cred_content = f"{user_content}:{pass_content}"
encoded_cred_content = base64.b64encode(cred_content.encode()).decode()

headers_content = {
    "Authorization": f"Basic {encoded_cred_content}",
    "Accept": "application/json"
}

# Credenciais para o export de reservas
username_res = "09af95bc"
password_res = "3c4699d1"
credentials_res = f"{username_res}:{password_res}"
encoded_credentials_res = base64.b64encode(credentials_res.encode()).decode()

headers_reservas = {
    "Authorization": f"Basic {encoded_credentials_res}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

print("Buscando o grupo 'Governança Amanda' para filtrar os imóveis corretos...")

# PASSO 1: Achar o grupo "Governança Amanda" paginando com skip de 20 em 20
listing_ids_permitidos = []
skip = 0
encontrou_grupo = False

while not encontrou_grupo:
    url_groups = f"{base_url}/external/v1/content/groups?skip={skip}"
    resp_groups = requests.get(url_groups, headers=headers_content)
    
    if resp_groups.status_code == 200:
        grupos = resp_groups.json()
        if not grupos: 
            break
            
        for g in grupos:
            if g.get("internalName") == "Governança Amanda":
                listing_ids_permitidos = g.get("listingIds", [])
                encontrou_grupo = True
                print(f"Grupo 'Governança Amanda' encontrado! Total de imóveis no grupo: {len(listing_ids_permitidos)}")
                break
        skip += 20
    else:
        print(f"Erro ao buscar grupos: {resp_groups.status_code}")
        break

if not listing_ids_permitidos:
    print("Aviso: O grupo 'Governança Amanda' não foi encontrado ou está vazio. Prosseguindo sem filtro de grupo.")

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

# Mecanismo de Tentativa Automática (Retry) para erros 500 da Stays
max_tentativas = 3
tentativa = 0
response = None

while tentativa < max_tentativas:
    tentativa += 1
    try:
        response = requests.post(endpoint, headers=headers_reservas, json=payload, timeout=30)
        if response.status_code == 200:
            break
        elif response.status_code >= 500:
            print(f"Servidor da Stays instável (Erro {response.status_code}). Tentativa {tentativa} de {max_tentativas}. Aguardando 15 segundos...")
            time.sleep(15)
        else:
            break
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão na tentativa {tentativa}: {e}. Tentando novamente em 15 segundos...")
        time.sleep(15)

# Processamento e Filtragem após as tentativas
if response and response.status_code == 200:
    reservas = response.json()
    print(f"Sucesso! {len(reservas)} reservas brutas encontradas. Aplicando filtro do grupo...")
    
    lista_processada = []
    
# Vamos inspecionar a primeira reserva para entendermos o formato exato da Stays
    if len(reservas) > 0:
        print("--- DIAGNÓSTICO DA PRIMEIRA RESERVA ---")
        print(reservas[0])
        print("---------------------------------------")

for r in reservas:
        # Pega o ID do imóvel dentro do dicionário 'listing' (ex: 'RK01I')
        listing_info = r.get("listing", {})
        id_imovel = listing_info.get("id")
        
        # Caso alternativo caso venha direto em outro campo
        if not id_imovel:
            id_imovel = r.get("_idlisting") or r.get("listingId")

        # Tratamento para isMaster (caso venha agrupado, pega o child)
        if r.get("isMaster") == True:
            childs = r.get("childs", [])
            if childs:
                id_imovel = childs[0].get("id") or childs[0].get("_idlisting")

        # Se identificamos um filtro de grupo, descarta o que estiver fora dele
        if listing_ids_permitidos and id_imovel not in listing_ids_permitidos:
            continue  # Pula esta reserva pois não pertence ao "Governança Amanda"

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
    
    # Criando o DataFrame FORA do loop com segurança
    df = pd.DataFrame(lista_processada)
    
    if not df.empty:
        df["Check-in"] = pd.to_datetime(df["Check-in"]).dt.strftime('%Y-%m-%d')
        df["Check-out"] = pd.to_datetime(df["Check-out"]).dt.strftime('%Y-%m-%d')
        df = df.sort_values(by="Check-in", ascending=True)
        print(f"Processamento concluído. {len(df)} reservas válidas após o filtro do grupo.")
    else:
        print("Nenhuma reserva encontrada para o grupo no período.")
        df = pd.DataFrame(columns=[
            "Check-in", "Check-out", "Unidade / Apto", "Hóspedes", 
            "Travesseiros", "Fronhas", "Jogos de Lençóis", "Cobertores", 
            "Panos de Prato", "Toalhas de Rosto", "Toalhas de Banho"
        ])
else:
    status = response.status_code if response else "Desconhecido"
    text = response.text if response else "Sem resposta"
    raise Exception(f"Erro ao buscar reservas na Stays após {max_tentativas} tentativas: {status} - {text}")    

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
    msg['To'] = "studioclean013@gmail.com"
    
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
enviar_email_atualizacao("https://docs.google.com/spreadsheets/d/15eNX1NkBrUG3AhEaiaoFw39h_z4Pj-0ulqGk6vJgpVQ/edit?usp=drive_link", "studioclean013@gmail.com")
