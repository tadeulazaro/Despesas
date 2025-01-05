from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    type = db.Column(db.String(10), nullable=False, default='saida')  # entrada ou saída

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

# Rotas

@app.route('/')
def index():
    # Recupera todas as despesas e categorias do banco de dados
    expenses = Expense.query.all()
    categories = Category.query.all()

    # Calculando valores e labels para o gráfico
    category_totals = {}
    for expense in expenses:
        if expense.category not in category_totals:
            category_totals[expense.category] = 0
        category_totals[expense.category] += expense.value

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    # Calculando os totais de entrada e saída
    total_entrada = sum(e.value for e in expenses if e.type == 'entrada')
    total_saida = sum(e.value for e in expenses if e.type == 'saida')
    saldo = total_entrada - total_saida

    # Renderiza o template com os dados necessários
    return render_template(
        'index.html',
        expenses=expenses,
        categories=categories,  # Passa as categorias reais do banco
        total_entrada=total_entrada,
        total_saida=total_saida,
        saldo=saldo,
        values=values,
        labels=labels,
    )

@app.route('/add', methods=['POST'])
def add_expense():
    try:
        # Captura dos dados do formulário
        description = request.form.get('description')
        category = request.form.get('category')
        value = request.form.get('value')
        date = request.form.get('date')
        type = request.form.get('type')

        # Validações
        if not all([description, category, value, date, type]):
            return "Todos os campos são obrigatórios.", 400
        
        # Verifica se o valor da despesa é positivo
        value = float(value)
        if value <= 0:
            return "O valor da despesa deve ser positivo.", 400
        
        # Conversões
        date = datetime.strptime(date, '%Y-%m-%d')

        if type not in ['entrada', 'saida']:
            return "Tipo inválido.", 400

        # Inserção no banco de dados
        new_expense = Expense(description=description, category=category, value=value, date=date, type=type)
        db.session.add(new_expense)
        db.session.commit()

        return redirect(url_for('index'))
    except ValueError:
        return "Valor ou data inválidos.", 400
    except Exception as e:
        return f"Erro ao adicionar despesa: {e}", 500

@app.route('/add_category', methods=['POST'])
def add_category():
    try:
        name = request.form.get('category_name')
        if not name:
            return "Nome da categoria é obrigatório.", 400

        if Category.query.filter_by(name=name).first():
            return "Categoria já existe.", 400

        new_category = Category(name=name)
        db.session.add(new_category)
        db.session.commit()

        return redirect(url_for('index'))
    except Exception as e:
        return f"Erro ao adicionar categoria: {e}", 500

@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    
    if request.method == 'POST':
        # Atualizar os dados com as novas informações
        expense.description = request.form['description']
        expense.category = request.form['category']
        expense.value = float(request.form['value'])
        expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        expense.type = request.form['type']
        
        # Salvar as alterações no banco de dados
        db.session.commit()
        return redirect(url_for('index'))
    
    categories = Category.query.all()
    return render_template('edit_expense.html', expense=expense, categories=categories)

@app.route('/delete/<int:expense_id>', methods=['GET', 'POST'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    
    # Excluir a despesa
    db.session.delete(expense)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/category_chart')
def category_chart():
    # Obter as despesas agrupadas por categoria
    categories = db.session.query(Expense.category, db.func.sum(Expense.value).label('total')) \
        .group_by(Expense.category).all()

    # Criar as listas de rótulos e valores para o gráfico
    labels = [category[0] for category in categories]
    values = [category[1] for category in categories]

    # Passando as listas para o template
    return render_template('category_chart.html', labels=labels, values=values)

@app.route('/summary')
def summary():
    expenses = Expense.query.all()
    total_entrada = sum(e.value for e in expenses if e.type == 'entrada')
    total_saida = sum(e.value for e in expenses if e.type == 'saida')
    saldo = total_entrada - total_saida

    # Cálculo por categoria
    category_expenses = {}
    for expense in expenses:
        if expense.category not in category_expenses:
            category_expenses[expense.category] = 0
        category_expenses[expense.category] += expense.value

    # Preparando os dados para o gráfico
    labels = list(category_expenses.keys())
    values = list(category_expenses.values())

    return render_template(
        'summary.html',
        total_entrada=total_entrada,
        total_saida=total_saida,
        saldo=saldo,
        labels=labels,
        values=values
    )

@app.route('/report', methods=['GET'])
def report():
    # Recupera parâmetros de filtros
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    type_filter = request.args.get('type')

    query = Expense.query

    # Filtra por data
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Expense.date >= start_date)
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(Expense.date <= end_date)

    # Filtra por categoria
    if category:
        query = query.filter(Expense.category == category)

    # Filtra por tipo
    if type_filter:
        query = query.filter(Expense.type == type_filter)

    expenses = query.all()
    return render_template('report.html', expenses=expenses)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
