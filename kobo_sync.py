import os
import requests
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 1. Configurações de Acesso ---
KOBO_URL = "https://kf.kobotoolbox.org"
ASSET_UID = "aoXMqam2RfsKFvZVPkQdn6"
TOKEN = "a21c8e2faa2199f313a9bbdc231f405078fbf2b6"
PASTA_FOTOS_ID = "1yvy6cFjjVDs6nZ2FKDySDR9DNb1zNaI_"

HEADERS = {
    "Authorization": f"Token {TOKEN}"
}

# Credenciais OAuth fornecidas pelo usuário
OAUTH_CLIENT_ID = "264717223506-s4obgob0rflc3bi9jfs3jufi1unju1ff.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//01YRTKf4C1z-9CgYIARAAGAESNwF-L9IrxM6LpTWB8XMQBbpeqGTCG6C82bBe25e39qBfToNkAS_gqecBnqXe0Z2--JuLupsftqg"

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

def autenticar_google():
    """Autentica no Drive via OAuth pessoal e nas Planilhas via gspread"""
    # Credenciais OAuth para o Google Drive (usando a sua conta com 400GB)
    drive_creds = OAuthCredentials(
        None,
        refresh_token=OAUTH_REFRESH_TOKEN,
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    drive_service = build("drive", "v3", credentials=drive_creds)
    
    # Para o gspread (Planilhas), usamos explicitamente a classe da Conta de Serviço
    sheet_creds = ServiceAccountCredentials.from_service_account_file("credentials.json", scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])
    gspread_client = gspread.authorize(sheet_creds)
    
    return drive_service, gspread_client

def extrair_dados_kobo():
    url = f"{KOBO_URL}/api/v2/assets/{ASSET_UID}/data/"
    print("Conectando ao KoboToolbox para extrair as vistorias e mídias...")
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

def processar_registros_e_midias(dados, drive_service):
    lista_processada = []
    os.makedirs("temp_fotos", exist_ok=True)

    for reg in dados:
        reg_id = reg.get('_id')        
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

        # Processamento de anexos (Download do Kobo -> Upload para o Drive via OAuth)
        attachments = reg.get("_attachments", [])
        mapa_links_attachments = {}
        
        if attachments:
            for att in attachments:
                download_url = att.get("download_url")
                filename = att.get("media_file_basename")
                
                if download_url and filename:
                    resp_foto = requests.get(download_url, headers=HEADERS)
                    if resp_foto.status_code == 200:
                        caminho_local = os.path.join("temp_fotos", filename)
                        with open(caminho_local, "wb") as f:
                            f.write(resp_foto.content)
                        
                        # Upload para o Google Drive na pasta Historico_Kobo_Fotos usando a conta pessoal
                        nome_no_drive = f"Vistoria_{reg_id}_{filename}"
                        file_metadata = {
                            'name': nome_no_drive,
                            'parents': [PASTA_FOTOS_ID]
                        }
                        media = MediaFileUpload(caminho_local, mimetype='image/jpeg', resumable=True)
                        
                        try:
                            file_drive = drive_service.files().create(
                                body=file_metadata,
                                media_body=media,
                                fields='id, webViewLink'
                            ).execute()
                            
                            link_visualizacao = file_drive.get('webViewLink', '')
                            mapa_links_attachments[filename] = link_visualizacao
                        except Exception as e:
                            print(f"Erro no upload da foto {filename}: {e}")
                        
                        if os.path.exists(caminho_local):
                            os.remove(caminho_local)

        # Função auxiliar segura para buscar o link da foto (só busca se o campo existir no registro)
        def obter_link_foto(campo_kobo):
            if campo_kobo not in reg:
                return ""
            nome_arquivo = reg.get(campo_kobo, "")
            if not nome_arquivo:
                return ""
            for arq_base, link in mapa_links_attachments.items():
                if nome_arquivo in arq_base:
                    return link
            return nome_arquivo

        # Cálculo dinâmico da porcentagem com o prefixo correto grp_arrumacao/
        chaves_checklist = [
            "grp_arrumacao/grp_banheiro1/b1_cabelos", "grp_arrumacao/grp_banheiro1/b1_box", "grp_arrumacao/grp_banheiro1/b1_rack_piso", "grp_arrumacao/grp_banheiro1/b1_acessorios", "grp_arrumacao/grp_banheiro1/b1_sabonete", "grp_arrumacao/grp_banheiro1/b1_toalhas", "grp_arrumacao/grp_banheiro1/b1_papel", "grp_arrumacao/grp_banheiro1/b1_torneiras", "grp_arrumacao/grp_banheiro1/b1_funcional",
            "grp_arrumacao/grp_banheiro2/b2_cabelos", "grp_arrumacao/grp_banheiro2/b2_box", "grp_arrumacao/grp_banheiro2/b2_rack_piso", "grp_arrumacao/grp_banheiro2/b2_acessorios", "grp_arrumacao/grp_banheiro2/b2_sabonete", "grp_arrumacao/grp_banheiro2/b2_toalhas", "grp_arrumacao/grp_banheiro2/b2_papel", "grp_arrumacao/grp_banheiro2/b2_torneiras", "grp_arrumacao/grp_banheiro2/b2_funcional",
            "grp_arrumacao/grp_banheiro3/b3_cabelos", "grp_arrumacao/grp_banheiro3/b3_box", "grp_arrumacao/grp_banheiro3/b3_rack_piso", "grp_arrumacao/grp_banheiro3/b3_acessorios", "grp_arrumacao/grp_banheiro3/b3_sabonete", "grp_arrumacao/grp_banheiro3/b3_toalhas", "grp_arrumacao/grp_banheiro3/b3_papel", "grp_arrumacao/grp_banheiro3/b3_torneiras", "grp_arrumacao/grp_banheiro3/b3_funcional",
            "grp_arrumacao/grp_banheiro4/b4_cabelos", "grp_arrumacao/grp_banheiro4/b4_box", "grp_arrumacao/grp_banheiro4/b4_rack_piso", "grp_arrumacao/grp_banheiro4/b4_acessorios", "grp_arrumacao/grp_banheiro4/b4_sabonete", "grp_arrumacao/grp_banheiro4/b4_toalhas", "grp_arrumacao/grp_banheiro4/b4_papel", "grp_arrumacao/grp_banheiro4/b4_torneiras", "grp_arrumacao/grp_banheiro4/b4_funcional",
            "grp_arrumacao/grp_sala/sala_controles", "grp_arrumacao/grp_sala/sala_varanda", "grp_arrumacao/grp_sala/sala_moveis", "grp_arrumacao/grp_sala/sala_portas", "grp_arrumacao/grp_sala/sala_sofa", "grp_arrumacao/grp_sala/sala_embaixo",
            "grp_arrumacao/grp_quarto1/q1_enxoval", "grp_arrumacao/grp_quarto1/q1_kit", "grp_arrumacao/grp_quarto1/q1_cobertores", "grp_arrumacao/grp_quarto1/q1_armario", "grp_arrumacao/grp_quarto1/q1_enxoval_gd", "grp_arrumacao/grp_quarto1/q1_cama_emb",
            "grp_arrumacao/grp_quarto2/q2_enxoval", "grp_arrumacao/grp_quarto2/q2_kit", "grp_arrumacao/grp_quarto2/q2_cobertores", "grp_arrumacao/grp_quarto2/q2_armario", "grp_arrumacao/grp_quarto2/q2_enxoval_gd", "grp_arrumacao/grp_quarto2/q2_cama_emb",
            "grp_arrumacao/grp_quarto3/q3_enxoval", "grp_arrumacao/grp_quarto3/q3_kit", "grp_arrumacao/grp_quarto3/q3_cobertores", "grp_arrumacao/grp_quarto3/q3_armario", "grp_arrumacao/grp_quarto3/q3_enxoval_gd", "grp_arrumacao/grp_quarto3/q3_cama_emb",
            "grp_arrumacao/grp_cozinha/coz_panoprato", "grp_arrumacao/grp_cozinha/coz_loucas_num", "grp_arrumacao/grp_cozinha/coz_geladeira", "grp_arrumacao/grp_cozinha/coz_panelas", "grp_arrumacao/grp_cozinha/coz_temp_gel", "grp_arrumacao/grp_cozinha/coz_escorredor", "grp_arrumacao/grp_cozinha/coz_lixeira", "grp_arrumacao/grp_cozinha/coz_forno", "grp_arrumacao/grp_cozinha/coz_cafe", "grp_arrumacao/grp_cozinha/coz_sacos_lixo", "grp_arrumacao/grp_cozinha/coz_placa", "grp_arrumacao/grp_cozinha/coz_armario_ch", "grp_arrumacao/grp_cozinha/coz_gas",
            "grp_arrumacao/grp_jacuzzi/jac_limpa", "grp_arrumacao/grp_jacuzzi/jac_desinf"
        ]

        total_itens = 0
        itens_ok = 0
        for chave in chaves_checklist:
            if chave in reg:
                total_itens += 1
                valor = reg.get(chave)
                # --- LINHA DE DIAGNÓSTICO TEMPORÁRIA ---
                print(f"DEBUG_VALOR - Chave: {chave} | Valor retornado pelo Kobo: '{valor}' (Tipo: {type(valor)})")
                # ----------------------------------------
                if valor in ["yes", "ok", "1", True]:
                    itens_ok += 1
        
        percentual_conclusao = round((itens_ok / total_itens * 100), 1) if total_itens > 0 else 0.0

        obs_vistoria = reg.get("grp_vistoria/vis_ocorrencias", "")
        obs_geral = reg.get("grp_arrumacao/grp_geral", reg.get("grp_geral", ""))
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
            "Conclusão (%)": f"{percentual_conclusao}%" if total_itens > 0 else "N/A (Apenas Vistoria)",
            "Ocorrências / Obs": ocorrencias_finais,
            "Enviado por": enviar_por,
            
            "Banheiro 1 - Foto 1": obter_link_foto("grp_arrumacao/grp_banheiro1/b1_foto1"),
            "Banheiro 1 - Foto 2": obter_link_foto("grp_arrumacao/grp_banheiro1/b1_foto2"),
            "Banheiro 1 - Obs": reg.get("grp_arrumacao/grp_banheiro1/b1_obs", ""),
            "Banheiro 2 - Foto 1": obter_link_foto("grp_arrumacao/grp_banheiro2/b2_foto1"),
            "Banheiro 2 - Foto 2": obter_link_foto("grp_arrumacao/grp_banheiro2/b2_foto2"),
            "Banheiro 2 - Obs": reg.get("grp_arrumacao/grp_banheiro2/b2_obs", ""),
            "Banheiro 3 - Foto 1": obter_link_foto("grp_arrumacao/grp_banheiro3/b3_foto1"),
            "Banheiro 3 - Foto 2": obter_link_foto("grp_arrumacao/grp_banheiro3/b3_foto2"),
            "Banheiro 3 - Obs": reg.get("grp_arrumacao/grp_banheiro3/b3_obs", ""),
            "Banheiro 4 - Foto 1": obter_link_foto("grp_arrumacao/grp_banheiro4/b4_foto1"),
            "Banheiro 4 - Foto 2": obter_link_foto("grp_arrumacao/grp_banheiro4/b4_foto2"),
            "Banheiro 4 - Obs": reg.get("grp_arrumacao/grp_banheiro4/b4_obs", ""),
            "Sala/Varanda - Foto 1": obter_link_foto("grp_arrumacao/grp_sala/sala_foto1"),
            "Sala/Varanda - Foto 2": obter_link_foto("grp_arrumacao/grp_sala/sala_foto2"),
            "Sala/Varanda - Obs": reg.get("grp_arrumacao/grp_sala/sala_obs", ""),
            "Quarto 1 - Foto 1": obter_link_foto("grp_arrumacao/grp_quarto1/q1_foto1"),
            "Quarto 1 - Foto 2": obter_link_foto("grp_arrumacao/grp_quarto1/q1_foto2"),
            "Quarto 1 - Obs": reg.get("grp_arrumacao/grp_quarto1/q1_obs", ""),
            "Quarto 2 - Foto 1": obter_link_foto("grp_arrumacao/grp_quarto2/q2_foto1"),
            "Quarto 2 - Foto 2": obter_link_foto("grp_arrumacao/grp_quarto2/q2_foto2"),
            "Quarto 2 - Obs": reg.get("grp_arrumacao/grp_quarto2/q2_obs", ""),
            "Quarto 3 - Foto 1": obter_link_foto("grp_arrumacao/grp_quarto3/q3_foto1"),
            "Quarto 3 - Foto 2": obter_link_foto("grp_arrumacao/grp_quarto3/q3_foto2"),
            "Quarto 3 - Obs": reg.get("grp_arrumacao/grp_quarto3/q3_obs", ""),
            "Cozinha - Foto 1": obter_link_foto("grp_arrumacao/grp_cozinha/coz_foto1"),
            "Cozinha - Foto 2": obter_link_foto("grp_arrumacao/grp_cozinha/coz_foto2"),
            "Cozinha - Obs": reg.get("grp_arrumacao/grp_cozinha/coz_obs", ""),
            "Jacuzzi - Foto 1": obter_link_foto("grp_arrumacao/grp_jacuzzi/jac_foto1"),
            "Jacuzzi - Foto 2": obter_link_foto("grp_arrumacao/grp_jacuzzi/jac_foto2"),
            "Jacuzzi - Obs": reg.get("grp_arrumacao/grp_jacuzzi/jac_obs", ""),
            "Registro Geral": reg.get("grp_arrumacao/grp_geral", reg.get("grp_geral", "")),
            "Danos Observados": reg.get("grp_arrumacao/obs_danos", reg.get("obs_danos", "")),
            "Foto Final 1": obter_link_foto("grp_arrumacao/grp_geral/foto_final1"),
            "Foto Final 2": obter_link_foto("grp_arrumacao/grp_geral/foto_final2"),
            "Foto Final 3": obter_link_foto("grp_arrumacao/grp_geral/foto_final3"),
            "Vídeo Final 1": obter_link_foto("grp_arrumacao/grp_geral/video_final1"),
            "Vídeo Final 2": obter_link_foto("grp_arrumacao/grp_geral/video_final2"),
            "Foto Vistoria 1": obter_link_foto("grp_vistoria/vis_foto1"),
            "Foto Vistoria 2": obter_link_foto("grp_vistoria/vis_foto2"),
            "Foto Vistoria 3": obter_link_foto("grp_vistoria/vis_foto3"),
            "Foto Vistoria 4": obter_link_foto("grp_vistoria/vis_foto4"),
            "Vídeo Vistoria 1": obter_link_foto("grp_vistoria/vis_video1"),
            "Vídeo Vistoria 2": obter_link_foto("grp_vistoria/vis_video2")
        }
        lista_processada.append(linha)

    return pd.DataFrame(lista_processada)

def atualizar_planilha_unica(df, gspread_client):
    if df.empty:
        print("Nenhum dado para enviar.")
        return

    nome_planilha = "Historico_Checklist_Kobo"
    
    try:
        spreadsheet = gspread_client.open(nome_planilha)
        sheet = spreadsheet.sheet1
        sheet.clear()
        print(f"Planilha fixa '{nome_planilha}' aberta e limpa com sucesso.")
    except Exception as e:
        print(f"Erro ao abrir a planilha fixa no Drive: {e}")
        return

    sheet.update(values=[df.columns.tolist()] + df.values.tolist(), range_name="A1")
    print("Sucesso absoluto! Planilha, porcentagem e links de fotos atualizados.")

if __name__ == "__main__":
    drive_service, gspread_client = autenticar_google()
    dados_brutos = extrair_dados_kobo()
    if dados_brutos:
        df_final = processar_registros_e_midias(dados_brutos, drive_service)
        atualizar_planilha_unica(df_final, gspread_client)
