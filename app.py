import os
from flask import Flask, render_template, request, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pdf_processor import processar_pdfs, gerar_pdf_unificado

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Orcamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_identificador = db.Column(db.String(150), nullable=False)
    ref_bling = db.Column(db.String(50)) 
    ref_sp = db.Column(db.String(50)) 
    ref_ue = db.Column(db.String(50)) 
    data_geracao = db.Column(db.DateTime, default=datetime.utcnow)
    valor_total = db.Column(db.Float, default=0.0)
    itens = db.relationship('Item', backref='orcamento', lazy=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id'), nullable=False)
    codigo = db.Column(db.String(100))
    descricao = db.Column(db.String(255))
    quantidade = db.Column(db.Float)
    unidade = db.Column(db.String(20))
    valor_unitario = db.Column(db.Float)
    valor_total = db.Column(db.Float)

with app.app_context():
    db.create_all()

# --- ROTA MÁGICA PARA ATUALIZAR O BANCO DE DADOS ---
@app.route('/atualizar-banco')
def atualizar_banco():
    db.drop_all()    # Apaga toda a estrutura velha travada
    db.create_all()  # Cria a estrutura nova e limpa
    return "<h1>Banco de dados atualizado com sucesso!</h1><p>Todas as colunas (incluindo a da Universo Elétrico) foram criadas.</p><a href='/'>Clique aqui para voltar ao sistema</a>"

@app.route('/', methods=['GET'])
def index():
    busca = request.args.get('busca', '')
    if busca:
        historico = Orcamento.query.filter(Orcamento.nome_identificador.ilike(f'%{busca}%')).order_by(Orcamento.data_geracao.desc()).all()
    else:
        historico = Orcamento.query.order_by(Orcamento.data_geracao.desc()).all()
    
    return render_template('index.html', historico=historico, busca=busca)

@app.route('/mesclar', methods=['POST'])
def mesclar():
    nome_identificador = request.form.get('nome_identificador')
    
    margem_ue_str = request.form.get('margem_ue', '0')
    try:
        margem_ue = float(margem_ue_str.replace(',', '.'))
    except:
        margem_ue = 0.0
    
    pdf_x = request.files.get('pdf_x')
    pdf_y = request.files.get('pdf_y')
    pdf_z = request.files.get('pdf_z') 

    itens_consolidados = []
    ref_bling_extraida = "N/A"
    ref_sp_extraida = "N/A"
    ref_ue_extraida = "N/A"
    
    if pdf_x and pdf_x.filename:
        itens, ref = processar_pdfs(pdf_x.read(), tipo='bling')
        itens_consolidados.extend(itens)
        if ref != "N/A": ref_bling_extraida = ref
        
    if pdf_y and pdf_y.filename:
        itens, ref = processar_pdfs(pdf_y.read(), tipo='system_port')
        itens_consolidados.extend(itens)
        if ref != "N/A": ref_sp_extraida = ref
        
    if pdf_z and pdf_z.filename:
        itens, ref = processar_pdfs(pdf_z.read(), tipo='universo_eletrico', margem=margem_ue)
        itens_consolidados.extend(itens)
        if ref != "N/A": ref_ue_extraida = ref

    if not itens_consolidados:
        return "Nenhum arquivo enviado ou erro na leitura da tabela.", 400

    total = sum(float(i.get('valor_total_num', 0)) for i in itens_consolidados)
    
    novo_orcamento = Orcamento(nome_identificador=nome_identificador, ref_bling=ref_bling_extraida, ref_sp=ref_sp_extraida, ref_ue=ref_ue_extraida, valor_total=total)
    db.session.add(novo_orcamento)
    db.session.commit()

    for item in itens_consolidados:
        novo_item = Item(
            orcamento_id=novo_orcamento.id,
            codigo=item.get('codigo', ''),
            descricao=item.get('descricao', ''),
            quantidade=item.get('quantidade', 0),
            unidade=item.get('unidade', ''),
            valor_unitario=item.get('valor_unitario_num', 0),
            valor_total=item.get('valor_total_num', 0)
        )
        db.session.add(novo_item)
    db.session.commit()

    pdf_buffer = gerar_pdf_unificado(itens_consolidados, novo_orcamento)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Proposta_{novo_orcamento.id}_{nome_identificador}.pdf", mimetype="application/pdf")

@app.route('/baixar_pdf/<int:id_orcamento>')
def baixar_pdf(id_orcamento):
    orcamento = Orcamento.query.get_or_404(id_orcamento)
    itens = []
    for item in orcamento.itens:
        itens.append({
            'codigo': item.codigo,
            'descricao': item.descricao,
            'quantidade': item.quantidade,
            'unidade': item.unidade,
            'valor_unitario_num': item.valor_unitario,
            'valor_total_num': item.valor_total
        })
        
    pdf_buffer = gerar_pdf_unificado(itens, orcamento)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Proposta_{orcamento.id}_{orcamento.nome_identificador}.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
