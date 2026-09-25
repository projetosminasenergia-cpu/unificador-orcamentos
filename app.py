import os
from flask import Flask, render_template, request, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pdf_processor import processar_pdfs, gerar_pdf_unificado

app = Flask(__name__)

# Conecta ao Neon usando a variável de ambiente do Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Orcamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_identificador = db.Column(db.String(150), nullable=False)
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

@app.route('/', methods=['GET'])
def index():
    historico = Orcamento.query.order_by(Orcamento.data_geracao.desc()).all()
    return render_template('index.html', historico=historico)

@app.route('/mesclar', methods=['POST'])
def mesclar():
    nome_identificador = request.form.get('nome_identificador')
    pdf_x = request.files.get('pdf_x')
    pdf_y = request.files.get('pdf_y')

    itens_consolidados = []
    
    if pdf_x and pdf_x.filename:
        itens_consolidados.extend(processar_pdfs(pdf_x.read(), tipo='bling'))
    if pdf_y and pdf_y.filename:
        itens_consolidados.extend(processar_pdfs(pdf_y.read(), tipo='system_port'))

    if not itens_consolidados:
        return "Nenhum arquivo enviado ou erro na leitura da tabela. Verifique o layout do PDF.", 400

    total = sum(float(i.get('valor_total_num', 0)) for i in itens_consolidados)
    novo_orcamento = Orcamento(nome_identificador=nome_identificador, valor_total=total)
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

    pdf_buffer = gerar_pdf_unificado(itens_consolidados)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"{nome_identificador}.pdf", mimetype="application/pdf")

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
        
    pdf_buffer = gerar_pdf_unificado(itens)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"{orcamento.nome_identificador}.pdf", mimetype="application/pdf")

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
