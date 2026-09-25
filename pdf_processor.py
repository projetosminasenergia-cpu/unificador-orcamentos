import pdfplumber
import io
import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

def limpar_numero(texto):
    t = str(texto).replace('R$', '').strip()
    t = ''.join(c for c in t if c.isdigit() or c in '.,')
    if not t: return 0.0
    
    if t.count(',') > 1:
        parts = t.rsplit(',', 1)
        t = parts[0].replace(',', '') + '.' + parts[1]
    elif t.count('.') > 1:
        parts = t.rsplit('.', 1)
        t = parts[0].replace('.', '') + '.' + parts[1]
    elif '.' in t and ',' in t:
        if t.rfind(',') > t.rfind('.'): t = t.replace('.', '').replace(',', '.')
        else: t = t.replace(',', '')
    elif ',' in t: 
        t = t.replace(',', '.')
        
    try: return float(t)
    except: return 0.0

def gerar_qr_code(link):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="#F4F6F9")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def processar_pdfs(pdf_bytes, tipo, margem=0.0):
    itens_extraidos = []
    referencia = "N/A"
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            
            # --- 1. LEITURA DAS REFERÊNCIAS ---
            if texto:
                linhas_texto = [linha.strip() for linha in texto.split('\n') if linha.strip()]
                for i, linha in enumerate(linhas_texto):
                    if tipo == 'bling' and "PROPOSTA N" in linha.upper():
                        numeros = ''.join(c for c in linha if c.isdigit())
                        if numeros: referencia = numeros
                    
                    elif tipo == 'system_port' and "ORÇAMENTO SIMPLES" in linha.upper():
                        for prox_linha in linhas_texto[i+1:i+4]:
                            possivel_ref = ''.join(c for c in prox_linha if c.isdigit())
                            if len(possivel_ref) >= 4:
                                referencia = possivel_ref
                                break
                                
                    elif tipo == 'universo_eletrico' and "ORCAMENTO N" in linha.upper():
                        partes = linha.upper().split("ORCAMENTO N")
                        if len(partes) > 1:
                            numeros = ''.join(c for c in partes[1].split('[')[0] if c.isdigit())
                            if numeros: referencia = numeros

            # --- 2. EXTRAÇÃO DOS PRODUTOS ---
            if tipo == 'universo_eletrico':
                if texto:
                    linhas_texto = texto.split('\n')
                    for linha in linhas_texto:
                        parts = linha.strip().split()
                        if len(parts) >= 4:
                            v_tot_str = parts[-1]
                            v_unit_str = parts[-2]
                            
                            if (',' in v_tot_str or '.' in v_tot_str) and (',' in v_unit_str or '.' in v_unit_str):
                                v_tot_base = limpar_numero(v_tot_str)
                                v_unit_base = limpar_numero(v_unit_str)
                                
                                if v_unit_base > 0 and v_tot_base > 0:
                                    cod = parts[0]
                                    if len(cod) <= 3 and parts[1].isdigit():
                                        cod = parts[1]
                                        desc = " ".join(parts[2:-2])
                                    else:
                                        desc = " ".join(parts[1:-2])
                                        
                                    if "DESCRIC" in desc.upper() or "TOTAL" in desc.upper(): continue
                                    if cod.isalpha(): continue
                                    
                                    unid = "UN"
                                    qtd = round(v_tot_base / v_unit_base, 2)
                                    
                                    fator = 1 + (margem / 100.0)
                                    v_unit = round(v_unit_base * fator, 2)
                                    v_tot = round(qtd * v_unit, 2)
                                    
                                    itens_extraidos.append({
                                        "codigo": cod[:100], "descricao": desc[:250], 
                                        "quantidade": qtd, "unidade": unid, 
                                        "valor_unitario_num": v_unit, "valor_total_num": v_tot
                                    })
            else:
                tabelas = page.extract_tables()
                for tabela in tabelas:
                    for linha in tabela:
                        l_bruta = [str(celula).strip() if celula else "" for celula in linha]
                        l = [c for c in l_bruta if c != ""]
                        if not l: continue
                        texto_linha = " ".join(l).upper()

                        if "CÓDIGO" in texto_linha or "DESCRIÇÃO" in texto_linha or "SOMA DAS" in texto_linha: continue
                        if "VENCIMENTO" in texto_linha or "TOTAL" in texto_linha or "Nº DE ITENS" in texto_linha: continue
                        if "IMAGEM" in texto_linha or "AVISTA" in texto_linha or "ÍTEM" in texto_linha: continue

                        try:
                            if tipo == 'bling':
                                if len(l) < 7: continue 
                                cod, desc, unid = l[2], l[1].replace('\n', ' '), l[3]
                                qtd, v_unit, v_tot = limpar_numero(l[4]), limpar_numero(l[5]), limpar_numero(l[6])
                            else: 
                                if len(l) < 7: continue 
                                cod, desc, unid = l[1], l[2].replace('\n', ' '), l[3]
                                qtd, v_unit, v_tot = limpar_numero(l[4]), limpar_numero(l[5]), limpar_numero(l[6])

                            if qtd == 0 and v_unit == 0: continue
                            itens_extraidos.append({"codigo": cod[:100], "descricao": desc[:250], "quantidade": qtd, "unidade": unid[:20], "valor_unitario_num": v_unit, "valor_total_num": v_tot})
                        except Exception as e:
                            continue
                        
    return itens_extraidos, referencia

def gerar_pdf_unificado(itens, orcamento_db):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=25, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    estilo_normal = styles['Normal']
    estilo_desc = ParagraphStyle('Descricao', parent=styles['Normal'], fontSize=8, leading=10)
    estilo_direita = ParagraphStyle('Direita', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    estilo_centro_bold = ParagraphStyle('CentroBold', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold', textColor=colors.white)

    try:
        logo = RLImage('logo.png', width=140, height=70)
    except:
        logo = Paragraph("<b>MINAS MATERIAIS ELÉTRICOS</b>", estilo_normal)

    dados_empresa = """<b>MINAS MATERIAIS ELÉTRICOS LTDA</b><br/>
                       Rua José Botelho Moreira, N° 394, LOTE 07<br/>
                       35431404 - Ponte Nova, MG<br/>
                       Telefone: (31) 99585-2164 | CNPJ: 64.705.243/0001-08"""
    
    tabela_cabecalho = Table([[logo, Paragraph(dados_empresa, estilo_direita)]], colWidths=[160, 375])
    tabela_cabecalho.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elements.append(tabela_cabecalho)
    elements.append(Spacer(1, 10))

    num_proposta_formatado = f"{300 + orcamento_db.id:05d}"
    data_hoje = orcamento_db.data_geracao.strftime("%d/%m/%Y")
    
    rastreabilidade = f"<font size=8>Ref. MM: {orcamento_db.ref_bling} | Ref. MP: {orcamento_db.ref_sp} | Ref. UE: {orcamento_db.ref_ue}</font>"

    dados_proposta = [
        [Paragraph(f"PROPOSTA COMERCIAL Nº {num_proposta_formatado}", estilo_centro_bold)],
        [Paragraph(f"<b>Projeto/Cliente:</b> {orcamento_db.nome_identificador}<br/><b>Data:</b> {data_hoje}<br/>{rastreabilidade}", estilo_normal)]
    ]
    
    tabela_identificacao = Table(dados_proposta, colWidths=[535])
    tabela_identificacao.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F2B705")),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F9F9F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#DDDDDD")),
        ('BOTTOMPADDING', (0,0), (-1,1), 8),
        ('TOPPADDING', (0,0), (-1,1), 8),
    ]))
    elements.append(tabela_identificacao)
    elements.append(Spacer(1, 15))

    dados_tabela = [["Código", "Descrição do produto", "Un", "Qtd", "V. Unitário", "V. Total"]]
    total_geral = 0.0
    soma_qtdes = 0.0
    
    for item in itens:
        v_unit_str = f"R$ {item.get('valor_unitario_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        v_tot_str = f"R$ {item.get('valor_total_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        total_geral += float(item.get('valor_total_num', 0))
        soma_qtdes += float(item.get('quantidade', 0))
        
        desc_paragraph = Paragraph(item.get('descricao', ''), estilo_desc)
        qtd_formatada = f"{item.get('quantidade', 0):.2f}".rstrip('0').rstrip('.') if item.get('quantidade', 0) % 1 != 0 else str(int(item.get('quantidade', 0)))

        dados_tabela.append([item.get('codigo', ''), desc_paragraph, item.get('unidade', ''), qtd_formatada, v_unit_str, v_tot_str])

    tabela_itens = Table(dados_tabela, colWidths=[60, 245, 30, 40, 75, 85])
    tabela_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#333333")), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 7),
        ('TOPPADDING', (0,0), (-1,0), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(tabela_itens)
    elements.append(Spacer(1, 15))

    total_formatado = f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    soma_qtdes_formatada = f"{soma_qtdes:.2f}".rstrip('0').rstrip('.') if soma_qtdes % 1 != 0 else str(int(soma_qtdes))
    
    dados_resumo = [
        ["N° de Itens", "Soma das Qtdes", "TOTAL DA PROPOSTA"],
        [str(len(itens)), soma_qtdes_formatada, total_formatado]
    ]
    
    tabela_resumo = Table(dados_resumo, colWidths=[100, 100, 140])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EAEAEA")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (2,1), (2,1), 'Helvetica-Bold'), 
        ('TEXTCOLOR', (2,1), (2,1), colors.HexColor("#1B5E20")), 
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BOTTOMPADDING', (0,0), (-1,1), 7),
        ('TOPPADDING', (0,0), (-1,1), 7),
    ]))
    tabela_resumo.hAlign = 'RIGHT'
    elements.append(tabela_resumo)
    elements.append(Spacer(1, 20))

    whatsapp_url = "https://wa.me/5531995852164?text=Ol%C3%A1%21%20Tudo%20bem%3F%0A%0ARecebi%20o%20or%C3%A7amento%20e%20gostaria%20de%20tirar%20algumas%20d%C3%BAvidas%20antes%20de%20prosseguir."
    qr_buffer = gerar_qr_code(whatsapp_url)
    img_qr = RLImage(qr_buffer, width=65, height=65)

    estilo_duvida_titulo = ParagraphStyle('DuvidaTitulo', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#1e2b4d"))
    estilo_duvida_texto = ParagraphStyle('DuvidaTexto', parent=styles['Normal'], fontSize=8, textColor=colors.gray)
    estilo_zap = ParagraphStyle('Zap', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_CENTER)
    
    # Olha que maravilha, nada de style="text-decoration:none;" aqui:
    btn_zap = Table([[Paragraph(f'<a href="{whatsapp_url}" color="white">Falar pelo WhatsApp</a>', estilo_zap)]], colWidths=[110], rowHeights=[22])
    btn_zap.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#25D366")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    bloco_esq = [
        Paragraph("Ficou com alguma dúvida sobre seu orçamento?", estilo_duvida_titulo),
        Spacer(1, 4),
        Paragraph("Nossa equipe está pronta para atendê-lo.", estilo_duvida_texto),
        Spacer(1, 8),
        btn_zap
    ]

    estilo_qr_texto = ParagraphStyle('QRTexto', parent=styles['Normal'], fontSize=7, textColor=colors.gray, alignment=TA_CENTER)
    bloco_meio = [
        Paragraph("Ou escaneie o QR Code<br/>para conversar conosco:", estilo_qr_texto),
        Spacer(1, 3),
        img_qr
    ]

    try:
        logo_ilustra = RLImage('logo.png', width=100, height=50)
    except:
        logo_ilustra = Paragraph(" ", estilo_normal)

    tabela_banner = Table([[bloco_esq, bloco_meio, logo_ilustra]], colWidths=[187, 161, 187])
    tabela_banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F4F6F9")), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (0,0), 15),
        ('RIGHTPADDING', (2,0), (2,0), 15),
    ]))
    elements.append(tabela_banner)
    
    estilo_rodape = ParagraphStyle('Rodape', parent=styles['Normal'], fontSize=8, textColor=colors.white)
    estilo_rodape_centro = ParagraphStyle('RodapeC', parent=estilo_rodape, alignment=TA_CENTER)
    estilo_rodape_dir = ParagraphStyle('RodapeD', parent=estilo_rodape, alignment=TA_RIGHT)
    
    # E nada de style aqui também:
    link_site = '<a href="https://www.minasmateriaiseletricos.com.br/" color="white">www.minasmateriaiseletricos.com.br</a>'
    
    tabela_rodape = Table([[Paragraph(link_site, estilo_rodape), Paragraph("Ponte Nova - MG", estilo_rodape_centro), Paragraph("(31) 99585-2164", estilo_rodape_dir)]], colWidths=[178, 179, 178])
    tabela_rodape.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1e2b4d")), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 15),
        ('RIGHTPADDING', (0,0), (-1,-1), 15),
    ]))
    elements.append(tabela_rodape)

    doc.build(elements)
    buffer.seek(0)
    return buffer
