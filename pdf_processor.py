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
                    if not linha or "Código" in str(linha[0]) or "Produto" in str(linha[0]):
                        continue
                    try:
                        # Extração inicial genérica (ajustaremos conforme o layout real dos seus PDFs)
                        qtd = str(linha[2] if tipo == 'bling' else linha[3]).replace(',', '.')
                        v_unit = str(linha[4]).replace('R$', '').replace('.', '').replace(',', '.').strip()
                        v_tot = str(linha[5]).replace('R$', '').replace('.', '').replace(',', '.').strip()
                        
                        item = {
                            "codigo": str(linha[0] if tipo == 'bling' else "N/A"),
                            "descricao": str(linha[1]).replace('\n', ' '),
                            "quantidade": float(qtd) if qtd.replace('.','',1).isdigit() else 0,
                            "unidade": str(linha[3] if tipo == 'bling' else linha[2]),
                            "valor_unitario_num": float(v_unit) if v_unit.replace('.','',1).isdigit() else 0,
                            "valor_total_num": float(v_tot) if v_tot.replace('.','',1).isdigit() else 0
                        }
                        itens_extraidos.append(item)
                    except Exception:
                        continue
    return itens_extraidos

def gerar_pdf_unificado(itens):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    header_text = "<b>MINAS MATERIAIS ELÉTRICOS LTDA</b><br/>CNPJ: 64.705.243/0001-08<br/>Orçamento Consolidado"
    elements.append(Paragraph(header_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    dados_tabela = [["Código", "Descrição", "Unid", "Qtd", "V. Unit", "V. Total"]]
    total_geral = 0.0
    
    for item in itens:
        v_unit_str = f"R$ {item.get('valor_unitario_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        v_tot_str = f"R$ {item.get('valor_total_num', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        total_geral += float(item.get('valor_total_num', 0))
        
        dados_tabela.append([
            item.get('codigo', ''),
            item.get('descricao', ''),
            item.get('unidade', ''),
            str(item.get('quantidade', '')),
            v_unit_str,
            v_tot_str
        ])

    total_formatado = f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    dados_tabela.append(["", "", "", "", "TOTAL GERAL:", total_formatado])

    t = Table(dados_tabela, colWidths=[60, 250, 40, 40, 70, 75])
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
    ]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer
