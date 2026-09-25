import pdfplumber
import io
import os
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
    if '.' in t and ',' in t:
        if t.rfind(',') > t.rfind('.'): t = t.replace('.', '').replace(',', '.')
        else: t = t.replace(',', '')
    elif ',' in t: t = t.replace(',', '.')
    try: return float(t)
    except: return 0.0

def processar_pdfs(pdf_bytes, tipo):
    itens_extraidos = []
    referencia = "N/A"
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            
            # 1. Tentar ler o número do orçamento no texto da página (Automatização)
            texto = page.extract_text()
            if texto:
                linhas_texto = texto.split('\n')
                for i, linha in enumerate(linhas_texto):
                    if tipo == 'bling' and "Proposta N" in linha:
                        # Corta a frase e pega só os números depois de "Proposta N°"
                        partes = linha.split("Proposta N")
                        if len(partes) > 1:
                            referencia = ''.join(c for c in partes[1] if c.isdigit())
                            
                    elif tipo == 'system_port' and "ORÇAMENTO SIMPLES" in linha.upper():
                        # No System Port, o número costuma estar na linha de baixo
                        if i + 1 < len(linhas_texto):
                            possivel_ref = linhas_texto[i+1].strip()
                            if possivel_ref.isdigit():
                                referencia = possivel_ref

            # 2. Ler as tabelas de itens
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
                            cod, desc, unid, qtd_str, v_unit_str, v_tot_str = l[2], l[1].replace('\n', ' '), l[3], l[4], l[5], l[6]
                        else: 
                            if len(l) < 7: continue 
                            cod, desc, unid, qtd_str, v_unit_str, v_tot_str = l[1], l[2].replace('\n', ' '), l[3], l[4], l[5], l[6]

                        qtd, v_unit, v_tot = limpar_numero(qtd_str), limpar_numero(v_unit_str), limpar_numero(v_tot_str)
                        if qtd == 0 and v_unit == 0: continue

                        itens_extraidos.append({"codigo": cod[:100], "descricao": desc[:250], "quantidade": qtd, "unidade": unid[:20], "valor_unitario_num": v_unit, "valor_total_num": v_tot})
                    except Exception as e:
                        continue
                        
    return itens_extraidos, referencia

def gerar_pdf_unificado(itens, orcamento_db):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    estilo_normal = styles['Normal']
    estilo_desc = ParagraphStyle('Descricao', parent=styles['Normal'], fontSize=8, leading=10)
    estilo_direita = ParagraphStyle('Direita', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    estilo_centro_bold = ParagraphStyle('CentroBold', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold', textColor=colors.white)

    try:
        logo = RLImage('logo.png', width=120, height=45)
    except:
        logo = Paragraph("<b>MINAS MATERIAIS ELÉTRICOS</b>", estilo_normal)

    dados_empresa = """<b>MINAS MATERIAIS ELÉTRICOS LTDA</b><br/>
                       Rua José Botelho Moreira, N° 394, LOTE 07<br/>
                       35431404 - Ponte Nova, MG<br/>
                       Telefone: (31) 99585-2164 | CNPJ: 64.705.243/0001-08"""
    
    tabela_cabecalho = Table([[logo, Paragraph(dados_empresa, estilo_direita)]], colWidths=[150, 385])
    tabela_cabecalho.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(tabela_cabecalho)
    elements.append(Spacer(1, 10))

    num_proposta_formatado = f"{300 + orcamento_db.id:05d}"
    data_hoje = orcamento_db.data_geracao.strftime("%d/%m/%Y")
    
    rastreabilidade = f"<font size=8>Ref. Bling: {orcamento_db.ref_bling} | Ref. MP: {orcamento_db.ref_sp}</font>"

    dados_proposta = [
        [Paragraph(f"PROPOSTA COMERCIAL Nº {num_proposta_formatado}", estilo_centro_bold)],
        [Paragraph(f"<b>Projeto/Cliente:</b> {orcamento_db.nome_identificador}<br/><b>Data:</b> {data_hoje}<br/>{rastreabilidade}", estilo_normal)]
    ]
    
    cor_marca = colors.HexColor("#F2B705") 
    tabela_identificacao = Table(dados_proposta, colWidths=[535])
    tabela_identificacao.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), cor_marca),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F9F9F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#DDDDDD")),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,1), (-1,1), 10),
        ('TOPPADDING', (0,1), (-1,1), 10),
    ]))
    elements.append(tabela_identificacao)
    elements.append(Spacer(1, 20))

    dados_tabela = [["Código", "Descrição do produto", "Un", "Qtd", "V. Unitário", "V. Total"]]
    total_geral = 0.0
    soma_qtdes = 0.0
    num_itens = len(itens)
    
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#404040")), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    elements.append(tabela_itens)
    elements.append(Spacer(1, 20))

    total_formatado = f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    soma_qtdes_formatada = f"{soma_qtdes:.2f}".rstrip('0').rstrip('.') if soma_qtdes % 1 != 0 else str(int(soma_qtdes))
    
    dados_resumo = [
        ["N° de Itens", "Soma das Qtdes", "TOTAL DA PROPOSTA"],
        [str(num_itens), soma_qtdes_formatada, total_formatado]
    ]
    
    tabela_resumo = Table(dados_resumo, colWidths=[100, 100, 140])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EAEAEA")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (2,1), (2,1), 'Helvetica-Bold'), 
        ('TEXTCOLOR', (2,1), (2,1), colors.HexColor("#B31B1B")), 
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    tabela_resumo.hAlign = 'RIGHT'
    elements.append(tabela_resumo)
    elements.append(Spacer(1, 40))

    elements.append(Paragraph("Atenciosamente,", estilo_normal))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Departamento de vendas</b><br/>Minas Materiais Elétricos", estilo_normal))

    doc.build(elements)
    buffer.seek(0)
    return buffer
