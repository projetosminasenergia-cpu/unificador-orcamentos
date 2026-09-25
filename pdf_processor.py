import pdfplumber
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

def processar_pdfs(pdf_bytes, tipo):
    itens_extraidos = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    l = [str(celula).strip() if celula else "" for celula in linha]
                    texto_linha = " ".join(l).upper()

                    if not texto_linha.strip(): continue
                    if "CÓDIGO" in texto_linha or "DESCRIÇÃO" in texto_linha or "SOMA DAS" in texto_linha: continue
                    if "VENCIMENTO" in texto_linha or "TOTAL" in texto_linha or "Nº DE ITENS" in texto_linha: continue
                    if "IMAGEM" in texto_linha or "AVISTA" in texto_linha: continue

                    try:
                        if tipo == 'bling':
                            if len(l) < 6: continue
                            cod = l[0]
                            desc = l[1].replace('\n', ' ')
                            qtd_str = l[2].replace(',', '.')
                            unid = l[3]
                            v_unit_str = l[4].replace('R$', '').replace('.', '').replace(',', '.')
                            v_tot_str = l[5].replace('R$', '').replace('.', '').replace(',', '.')
                        else:
                            if len(l) < 6: continue
                            cod = l[1]
                            desc = l[2].replace('\n', ' ')
                            unid = "UN"
                            qtd_str = l[3].replace(',', '.') if len(l) > 3 else "0"
                            v_unit_str = l[4].replace('R$', '').replace('.', '').replace(',', '.') if len(l) > 4 else "0"
                            v_tot_str = l[5].replace('R$', '').replace('.', '').replace(',', '.') if len(l) > 5 else v_unit_str

                        qtd = float(qtd_str) if qtd_str.replace('.','',1).isdigit() else 0.0
                        v_unit = float(v_unit_str) if v_unit_str.replace('.','',1).isdigit() else 0.0
                        v_tot = float(v_tot_str) if v_tot_str.replace('.','',1).isdigit() else (qtd * v_unit)

                        if qtd == 0 and v_unit == 0: continue

                        item = {
                            "codigo": cod[:100],
                            "descricao": desc[:250],
                            "quantidade": qtd,
                            "unidade": unid[:20],
                            "valor_unitario_num": v_unit,
                            "valor_total_num": v_tot
                        }
                        itens_extraidos.append(item)
                    except Exception as e:
                        continue
    return itens_extraidos

def gerar_pdf_unificado(itens):
    buffer = io.BytesIO()
    # Margens ajustadas para aproveitar melhor o espaço (A4 width = 595. 595 - 30 - 30 = 535)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos de texto personalizados
    estilo_normal = styles['Normal']
    estilo_desc = ParagraphStyle('Descricao', parent=styles['Normal'], fontSize=8, leading=10)
    estilo_direita = ParagraphStyle('Direita', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading2'], fontSize=14, spaceAfter=10)

    # --- 1. CABEÇALHO (Logo e Dados da Empresa) ---
    logo_texto = """<font size="16"><b>MINAS MATERIAIS ELÉTRICOS</b></font><br/><br/>
                    <font size="10">Orçamento Consolidado</font>"""
    
    dados_empresa = """<b>MINAS MATERIAIS ELETRICOS LTDA</b><br/>
                       Rua José Botelho Moreira, N° 394, LOTE 07<br/>
                       35431404 - Ponte Nova, MG<br/>
                       Telefone: (31) 99585-2164<br/>
                       CNPJ: 64.705.243/0001-08"""
    
    tabela_cabecalho = Table([
        [Paragraph(logo_texto, estilo_normal), Paragraph(dados_empresa, estilo_direita)]
    ], colWidths=[267, 268])
    tabela_cabecalho.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    
    elements.append(tabela_cabecalho)
    elements.append(Spacer(1, 15))

    # --- 2. DADOS DA PROPOSTA ---
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    info_proposta = f"<b>Data da emissão:</b> {data_hoje}"
    elements.append(Paragraph(info_proposta, estilo_normal))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("<b>Itens da proposta comercial</b>", estilo_titulo))

    # --- 3. TABELA DE ITENS ---
    # Cabeçalho da tabela igual ao Bling
    dados_tabela = [["Código", "Descrição do produto/serviço", "Un", "Qtd.", "Preço un.", "Preço total"]]
    
    total_geral = 0.0
    soma_qtdes = 0.0
    num_itens = len(itens)
    
    for item in itens:
        v_unit_str = f"R$ {item.get('valor_unitario_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        v_tot_str = f"R$ {item.get('valor_total_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        total_geral += float(item.get('valor_total_num', 0))
        soma_qtdes += float(item.get('quantidade', 0))
        
        # Paragraph para a descrição quebrar de linha sem desalinhar a tabela
        desc_paragraph = Paragraph(item.get('descricao', ''), estilo_desc)
        
        # Formatação de quantidade para remover o .0 se for inteiro
        qtd_formatada = f"{item.get('quantidade', 0):.2f}".rstrip('0').rstrip('.') if item.get('quantidade', 0) % 1 != 0 else str(int(item.get('quantidade', 0)))

        dados_tabela.append([
            item.get('codigo', ''),
            desc_paragraph,
            item.get('unidade', ''),
            qtd_formatada,
            v_unit_str,
            v_tot_str
        ])

    # Construção da tabela de itens
    tabela_itens = Table(dados_tabela, colWidths=[60, 245, 30, 40, 75, 85])
    tabela_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")), # Cinza claro no cabeçalho
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'), # Un, Qtd e Valores centralizados
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), # Bordas finas cinzas
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    elements.append(tabela_itens)
    elements.append(Spacer(1, 20))

    # --- 4. TABELA DE RESUMO (Fiel ao modelo) ---
    total_formatado = f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    soma_qtdes_formatada = f"{soma_qtdes:.2f}".rstrip('0').rstrip('.') if soma_qtdes % 1 != 0 else str(int(soma_qtdes))
    
    dados_resumo = [
        ["N° de Itens", "Soma das Qtdes", "Total da proposta"],
        [str(num_itens), soma_qtdes_formatada, total_formatado]
    ]
    
    tabela_resumo = Table(dados_resumo, colWidths=[100, 100, 120])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (2,1), (2,1), 'Helvetica-Bold'), # Total em negrito
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    
    # Alinhando a tabela de resumo à direita
    tabela_resumo.hAlign = 'RIGHT'
    elements.append(tabela_resumo)
    elements.append(Spacer(1, 40))

    # --- 5. RODAPÉ DE ASSINATURA ---
    elements.append(Paragraph("Atenciosamente,", estilo_normal))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Departamento de vendas</b>", estilo_normal))

    # Gera o arquivo
    doc.build(elements)
    buffer.seek(0)
    return buffer
