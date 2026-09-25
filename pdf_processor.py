import pdfplumber
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

def limpar_numero(texto):
    """Remove letras, símbolos de R$ e converte corretamente para decimal."""
    t = str(texto).replace('R$', '').strip()
    # Mantém apenas números, pontos e vírgulas
    t = ''.join(c for c in t if c.isdigit() or c in '.,')
    if not t: return 0.0
    
    # Tratamento para formatos tipo 1.000,50 ou apenas 271,15
    if '.' in t and ',' in t:
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        t = t.replace(',', '.')
        
    try:
        return float(t)
    except:
        return 0.0

def processar_pdfs(pdf_bytes, tipo):
    itens_extraidos = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    # Lê a linha bruta
                    l_bruta = [str(celula).strip() if celula else "" for celula in linha]
                    
                    # FILTRO MÁGICO: Remove colunas completamente vazias para evitar o "empurrão" de colunas
                    l = [c for c in l_bruta if c != ""]
                    
                    if not l: continue
                    texto_linha = " ".join(l).upper()

                    # Ignora linhas de cabeçalho, rodapé e informações de frete/vendedor
                    if "CÓDIGO" in texto_linha or "DESCRIÇÃO" in texto_linha or "SOMA DAS" in texto_linha: continue
                    if "VENCIMENTO" in texto_linha or "TOTAL" in texto_linha or "Nº DE ITENS" in texto_linha: continue
                    if "IMAGEM" in texto_linha or "AVISTA" in texto_linha or "ÍTEM" in texto_linha: continue

                    try:
                        # Mapeamento do Bling (Imagem, Descrição, Código, Un, Qtd, V.Un, V.Tot)
                        if tipo == 'bling':
                            if len(l) < 7: continue 
                            cod = l[2]
                            desc = l[1].replace('\n', ' ')
                            unid = l[3]
                            qtd_str = l[4]
                            v_unit_str = l[5]
                            v_tot_str = l[6]
                            
                        # Mapeamento do System Port (Item, Código, Descrição, Un, Qtd, V.Un, V.Tot)
                        else: 
                            if len(l) < 7: continue 
                            cod = l[1]
                            desc = l[2].replace('\n', ' ')
                            unid = l[3]
                            qtd_str = l[4]
                            v_unit_str = l[5]
                            v_tot_str = l[6]

                        # Conversão segura dos números
                        qtd = limpar_numero(qtd_str)
                        v_unit = limpar_numero(v_unit_str)
                        v_tot = limpar_numero(v_tot_str)

                        # Se quantidade e preço zerados, não é um produto
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
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    estilo_normal = styles['Normal']
    estilo_desc = ParagraphStyle('Descricao', parent=styles['Normal'], fontSize=8, leading=10)
    estilo_direita = ParagraphStyle('Direita', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9)
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading2'], fontSize=14, spaceAfter=10)

    # --- CABEÇALHO ---
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

    # --- DADOS DA PROPOSTA ---
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    info_proposta = f"<b>Data da emissão:</b> {data_hoje}"
    elements.append(Paragraph(info_proposta, estilo_normal))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("<b>Itens da proposta comercial</b>", estilo_titulo))

    # --- TABELA DE ITENS ---
    dados_tabela = [["Código", "Descrição do produto/serviço", "Un", "Qtd.", "Preço un.", "Preço total"]]
    
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

        dados_tabela.append([
            item.get('codigo', ''),
            desc_paragraph,
            item.get('unidade', ''),
            qtd_formatada,
            v_unit_str,
            v_tot_str
        ])

    tabela_itens = Table(dados_tabela, colWidths=[60, 245, 30, 40, 75, 85])
    tabela_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
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

    # --- TABELA DE RESUMO ---
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
        ('FONTNAME', (2,1), (2,1), 'Helvetica-Bold'), 
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    
    tabela_resumo.hAlign = 'RIGHT'
    elements.append(tabela_resumo)
    elements.append(Spacer(1, 40))

    # --- RODAPÉ ---
    elements.append(Paragraph("Atenciosamente,", estilo_normal))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Departamento de vendas</b>", estilo_normal))

    doc.build(elements)
    buffer.seek(0)
    return buffer
