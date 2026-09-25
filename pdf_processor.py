import pdfplumber
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def processar_pdfs(pdf_bytes, tipo):
    itens_extraidos = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tabelas = page.extract_tables()
            for tabela in tabelas:
                for linha in tabela:
                    # Limpa a linha e garante que tudo é texto
                    l = [str(celula).strip() if celula else "" for celula in linha]
                    texto_linha = " ".join(l).upper()

                    # Pula lixo (cabeçalhos, rodapés, imagens)
                    if not texto_linha.strip(): continue
                    if "CÓDIGO" in texto_linha or "DESCRIÇÃO" in texto_linha or "SOMA DAS" in texto_linha: continue
                    if "VENCIMENTO" in texto_linha or "TOTAL" in texto_linha or "Nº DE ITENS" in texto_linha: continue
                    if "IMAGEM" in texto_linha or "AVISTA" in texto_linha: continue

                    try:
                        # Extração do Bling
                        if tipo == 'bling':
                            if len(l) < 6: continue
                            cod = l[0]
                            desc = l[1].replace('\n', ' ')
                            qtd_str = l[2].replace(',', '.')
                            unid = l[3]
                            v_unit_str = l[4].replace('R$', '').replace('.', '').replace(',', '.')
                            v_tot_str = l[5].replace('R$', '').replace('.', '').replace(',', '.')
                        
                        # Extração Corrigida do System Port
                        else:
                            if len(l) < 6: continue
                            cod = l[1]
                            desc = l[2].replace('\n', ' ')
                            unid = "UN" # Forçamos UN pois o layout do System Port junta colunas
                            qtd_str = l[3].replace(',', '.') if len(l) > 3 else "0"
                            v_unit_str = l[4].replace('R$', '').replace('.', '').replace(',', '.') if len(l) > 4 else "0"
                            v_tot_str = l[5].replace('R$', '').replace('.', '').replace(',', '.') if len(l) > 5 else v_unit_str

                        # Transformação segura para números
                        qtd = float(qtd_str) if qtd_str.replace('.','',1).isdigit() else 0.0
                        v_unit = float(v_unit_str) if v_unit_str.replace('.','',1).isdigit() else 0.0
                        v_tot = float(v_tot_str) if v_tot_str.replace('.','',1).isdigit() else (qtd * v_unit)

                        # Se não for peça (preço e qtd zero), descarta
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
                        print("Ignorando linha problemática:", l)
                        continue
    return itens_extraidos

def gerar_pdf_unificado(itens):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # Criamos um estilo específico para a descrição, para ela quebrar de linha bonitinho
    estilo_desc = styles['Normal']
    estilo_desc.fontSize = 8 
    
    header_text = "<b>MINAS MATERIAIS ELÉTRICOS LTDA</b><br/>CNPJ: 64.705.243/0001-08<br/>Orçamento Consolidado"
    elements.append(Paragraph(header_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    dados_tabela = [["Código", "Descrição", "Unid", "Qtd", "V. Unit", "V. Total"]]
    total_geral = 0.0
    
    for item in itens:
        v_unit_str = f"R$ {item.get('valor_unitario_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        v_tot_str = f"R$ {item.get('valor_total_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        total_geral += float(item.get('valor_total_num', 0))
        
        # O Paragraph impede que o texto invada outras colunas
        desc_paragraph = Paragraph(item.get('descricao', ''), estilo_desc)
        
        dados_tabela.append([
            item.get('codigo', ''),
            desc_paragraph, # Usamos o paragraph aqui no lugar do texto simples
            item.get('unidade', ''),
            str(item.get('quantidade', '')),
            v_unit_str,
            v_tot_str
        ])

    total_formatado = f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    dados_tabela.append(["", "", "", "", "TOTAL GERAL:", total_formatado])

    t = Table(dados_tabela, colWidths=[60, 240, 30, 40, 65, 75])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f0f0")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-2), 1, colors.black),
        ('LINEABOVE', (4,-1), (5,-1), 1, colors.black),
        ('FONTNAME', (4,-1), (5,-1), 'Helvetica-Bold'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Alinha os textos ao meio
    ]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer
