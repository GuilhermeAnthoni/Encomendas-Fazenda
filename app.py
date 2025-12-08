import sqlite3
from flask import Flask, request, redirect, url_for, flash, session, render_template_string
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave-secreta-simples"  # troque em produção

# Webhooks do Discord
WEBHOOK_ENCOMENDAS = "https://discord.com/api/webhooks/1447371536582574193/gcX3hHxrt8JGDoyWHj4rtavNNnWF7cC5Hd_0drCtJ7j6fu_IJRiKFxCgtwpr7TekW_lf"
WEBHOOK_VENDAS = "https://discord.com/api/webhooks/1447372762875297894/iUiNTCZU6DI5xzWabVjIBqn8d6wS9yh_L70skG8Kgemgt5SykiluR-YRmvk6iWU2wA-k"

# ------------------ BANCO DE DADOS ------------------ #

def get_db():
    conn = sqlite3.connect("orders.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            contato TEXT NOT NULL,
            horario_entrega TEXT NOT NULL,
            produto TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            valor INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            criado_em TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

# ------------------ FUNÇÕES AUXILIARES ------------------ #

PRECOS = {
    "Pistol": 600,
    "Sub (SMG)": 800,
    "Fuzil (Rifle)": 1000,
    "C4": 5000
}

def enviar_webhook(url, conteudo=None, embed=None):
    """Envia mensagem para o webhook; se embed for passado, manda como box."""
    try:
        data = {}
        if conteudo:
            data["content"] = conteudo
        if embed:
            data["embeds"] = [embed]
        requests.post(url, json=data, timeout=5)
    except Exception:
        # Em produção, logar o erro
        pass

def contato_valido(contato: str) -> bool:
    # Formato: 3 dígitos, hífen, 3 dígitos (ex: 123-456)
    if len(contato) != 7:
        return False
    if contato[3] != "-":
        return False
    parte1 = contato[:3]
    parte2 = contato[4:]
    return parte1.isdigit() and parte2.isdigit()

# ------------------ TEMPLATES EM STRING ------------------ #

INDEX_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Encomendas de Munições</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            background: #111;
            color: #eee;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            flex-direction: column;
        }
        h1 {
            color: #f5c542;
            margin-bottom: 20px;
            text-align: center;
        }
        form {
            width: 400px;
            background: #222;
            padding: 20px;
            border-radius: 8px;
            margin: 0 auto;
        }
        label { display: block; margin-top: 10px; }
        input, select {
            width: 100%;
            padding: 8px;
            margin-top: 5px;
            border-radius: 4px;
            border: 1px solid #555;
            background: #111;
            color: #eee;
        }
        button {
            margin-top: 15px;
            padding: 10px;
            width: 100%;
            background: #f5c542;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
        }
        button:hover { background: #e0b233; }
        .flash { margin-top: 10px; padding: 8px; border-radius: 4px; }
        .flash.erro { background: #7b1e1e; }
        .notificacao {
            margin-top: 15px;
            padding: 10px;
            background: #1e7b2c;
            border-radius: 4px;
            width: 400px;
        }
        .precos {
            margin-top: 20px;
            width: 400px;
        }
        .precos ul { list-style: none; padding: 0; }
        .precos li { margin: 4px 0; }
        a { color: #f5c542; }

        /* aviso flutuante que some em 10s */
        .popup-aviso {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #222;
            color: #f5c542;
            padding: 15px 20px;
            border-radius: 8px;
            border: 1px solid #f5c542;
            box-shadow: 0 0 10px rgba(0,0,0,0.6);
            z-index: 9999;
        }
    </style>
</head>
<body>
    <h1>Encomendas de Munições & C4</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, msg in messages %}
          <div class="flash {{ category }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if mensagem_notificacao %}
        <div class="notificacao">{{ mensagem_notificacao }}</div>
        <div class="popup-aviso" id="popup-aviso">
            Entrega em até 24 horas ou aguarde contato In-game.
        </div>
    {% endif %}

    <form method="post">
        <label>Nome:</label>
        <input type="text" name="nome" required>

        <label>Contato (formato 000-000):</label>
        <input type="text" name="contato" placeholder="123-456" required>

        <label>Horário de entrega:</label>
        <input type="text" name="horario_entrega" placeholder="Ex: Após 20:00" required>

        <label>Produto:</label>
        <select name="produto" id="produto" required>
            <option value="">Selecione</option>
            <option value="Pistol">Pistol — D$ 600</option>
            <option value="Sub (SMG)">Sub (SMG) — D$ 800</option>
            <option value="Fuzil (Rifle)">Fuzil (Rifle) — D$ 1k</option>
            <option value="C4">C4 — D$ 5k</option>
        </select>

        <label>Quantidade:</label>
        <input type="number" name="quantidade" id="quantidade" value="1" min="1" required>

        <label>Total (D$):</label>
        <input type="text" id="total" readonly>

        <button type="submit">Fazer Encomenda</button>
    </form>

    <div class="precos">
        <h2>Tabela de preços</h2>
        <ul>
            <li>Pistol — D$ 600</li>
            <li>Sub (SMG) — D$ 800</li>
            <li>Fuzil (Rifle) — D$ 1k</li>
            <li>C4 — D$ 5k</li>
        </ul>
    </div>

    <p style="margin-top:20px;">
        Acesso de gerenciamento: <a href="{{ url_for('login') }}">Área de pedidos (restrita)</a>
    </p>

<script>
    // cálculo de total
    const precos = {
        "Pistol": 600,
        "Sub (SMG)": 800,
        "Fuzil (Rifle)": 1000,
        "C4": 5000
    };

    const selectProduto = document.getElementById('produto');
    const inputQuantidade = document.getElementById('quantidade');
    const inputTotal = document.getElementById('total');

    function formatarNumero(valor) {
        // separador de milhar com vírgula (1,000 / 5,000)
        return valor.toLocaleString('en-US');
    }

    function atualizarTotal() {
        const produto = selectProduto.value;
        const qtd = parseInt(inputQuantidade.value) || 1;
        if (produto in precos) {
            const total = precos[produto] * qtd;
            inputTotal.value = "D$ " + formatarNumero(total);
        } else {
            inputTotal.value = "";
        }
    }

    selectProduto.addEventListener('change', atualizarTotal);
    inputQuantidade.addEventListener('input', atualizarTotal);
    atualizarTotal();

    // esconder aviso em 10 segundos
    window.addEventListener('load', function () {
        const popup = document.getElementById('popup-aviso');
        if (popup) {
            setTimeout(function () {
                popup.style.display = 'none';
            }, 10000); // 10000 ms = 10s
        }
    });
</script>

</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Login - Pedidos</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #111; color: #eee; }
        h1 { color: #f5c542; }
        form { max-width: 300px; background: #222; padding: 20px; border-radius: 8px; }
        label { display: block; margin-top: 10px; }
        input { width: 100%; padding: 8px; margin-top: 5px; border-radius: 4px; border: 1px solid #555; background: #111; color: #eee; }
        button { margin-top: 15px; padding: 10px; width: 100%; background: #f5c542; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        button:hover { background: #e0b233; }
        .flash { margin-top: 10px; padding: 8px; border-radius: 4px; }
        .flash.erro { background: #7b1e1e; }
        a { color: #f5c542; }
    </style>
</head>
<body>
    <h1>Área Restrita</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, msg in messages %}
          <div class="flash {{ category }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
        <label>Senha de acesso:</label>
        <input type="password" name="senha" required>
        <button type="submit">Entrar</button>
    </form>

    <p style="margin-top:15px;">
        <a href="{{ url_for('index') }}">Voltar para encomendas</a>
    </p>
</body>
</html>
"""

PEDIDOS_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Pedidos de Encomendas</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #111; color: #eee; }
        h1 { color: #f5c542; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #444; padding: 8px; text-align: left; }
        th { background: #222; }
        tr:nth-child(even) { background: #1a1a1a; }
        form { display: inline; }
        button { padding: 5px 10px; background: #f5c542; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #e0b233; }
        a { color: #f5c542; }
    </style>
</head>
<body>
    <h1>Pedidos de Encomendas</h1>

    <p>
        <a href="{{ url_for('index') }}">Voltar para tela de encomendas</a>
    </p>

    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Nome</th>
                <th>Contato</th>
                <th>Horário entrega</th>
                <th>Produto</th>
                <th>Quantidade</th>
                <th>Valor</th>
                <th>Status</th>
                <th>Criado em</th>
                <th>Ações</th>
            </tr>
        </thead>
        <tbody>
            {% for o in orders %}
            <tr>
                <td>{{ o["id"] }}</td>
                <td>{{ o["nome"] }}</td>
                <td>{{ o["contato"] }}</td>
                <td>{{ o["horario_entrega"] }}</td>
                <td>{{ o["produto"] }}</td>
                <td>{{ o["quantidade"] }}</td>
                <td>D$ {{ o["valor"] }}</td>
                <td>{{ o["status"] }}</td>
                <td>{{ o["criado_em"] }}</td>
                <td>
                    <form method="post" action="{{ url_for('atualizar_status', pedido_id=o['id']) }}">
                        <select name="status">
                            <option value="PENDENTE" {% if o["status"] == "PENDENTE" %}selected{% endif %}>PENDENTE</option>
                            <option value="ENTREGUE" {% if o["status"] == "ENTREGUE" %}selected{% endif %}>ENTREGUE</option>
                        </select>
                        <button type="submit">Atualizar</button>
                    </form>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="10">Nenhuma encomenda registrada.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# ------------------ ROTAS ------------------ #

@app.route("/", methods=["GET", "POST"])
def index():
    mensagem_notificacao = None

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        contato = request.form.get("contato", "").strip()
        horario_entrega = request.form.get("horario_entrega", "").strip()
        produto = request.form.get("produto")
        quantidade_str = request.form.get("quantidade", "1")

        # Validações simples
        erros = []
        if not nome:
            erros.append("Nome é obrigatório.")
        if not contato_valido(contato):
            erros.append("Contato deve ter o formato 000-000 (6 dígitos com hífen).")
        if not horario_entrega:
            erros.append("Horário de entrega é obrigatório.")
        if produto not in PRECOS:
            erros.append("Produto inválido.")

        try:
            quantidade = int(quantidade_str)
            if quantidade < 1:
                raise ValueError
        except ValueError:
            erros.append("Quantidade deve ser um número inteiro maior ou igual a 1.")

        if erros:
            for e in erros:
                flash(e, "erro")
        else:
            valor_unitario = PRECOS[produto]
            valor = valor_unitario * quantidade

            conn = get_db()
            cur = conn.cursor()
            criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO orders (nome, contato, horario_entrega, produto, quantidade, valor, status, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDENTE', ?)
            """, (nome, contato, horario_entrega, produto, quantidade, valor, criado_em))
            conn.commit()
            pedido_id = cur.lastrowid
            conn.close()

            # Embed para Aba Encomendas
            embed = {
                "title": f"📦 Nova encomenda #{pedido_id}",
                "color": 0xF5C542,
                "fields": [
                    {"name": "Nome", "value": nome, "inline": True},
                    {"name": "Contato", "value": contato, "inline": True},
                    {"name": "Horário entrega", "value": horario_entrega, "inline": False},
                    {"name": "Produto", "value": produto, "inline": True},
                    {"name": "Quantidade", "value": str(quantidade), "inline": True},
                    {"name": "Valor total", "value": f"D$ {valor}", "inline": True},
                    {"name": "Status", "value": "PENDENTE", "inline": True},
                    {"name": "Prazo", "value": "Entrega em até 24 horas ou aguarde contato In-game.", "inline": False},
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            enviar_webhook(WEBHOOK_ENCOMENDAS, embed=embed)

            mensagem_notificacao = "Encomenda registrada! Prazo de 24hrs para entrega ou aguarde contato in-game."

    return render_template_string(INDEX_HTML, precos=PRECOS, mensagem_notificacao=mensagem_notificacao)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha == "77":
            session["autorizado"] = True
            return redirect(url_for("pedidos"))
        else:
            flash("Senha incorreta.", "erro")
    return render_template_string(LOGIN_HTML)

@app.route("/pedidos")
def pedidos():
    if not session.get("autorizado"):
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template_string(PEDIDOS_HTML, orders=orders)

@app.route("/atualizar_status/<int:pedido_id>", methods=["POST"])
def atualizar_status(pedido_id):
    if not session.get("autorizado"):
        return redirect(url_for("login"))

    novo_status = request.form.get("status")
    if novo_status not in ["PENDENTE", "ENTREGUE"]:
        flash("Status inválido.", "erro")
        return redirect(url_for("pedidos"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (novo_status, pedido_id))
    conn.commit()

    if novo_status == "ENTREGUE":
        cur.execute("SELECT * FROM orders WHERE id = ?", (pedido_id,))
        pedido = cur.fetchone()
        if pedido:
            embed = {
                "title": f"✅ Encomenda #{pedido['id']} ENTREGUE",
                "color": 0x1E7B2C,
                "fields": [
                    {"name": "Nome", "value": pedido["nome"], "inline": True},
                    {"name": "Contato", "value": pedido["contato"], "inline": True},
                    {"name": "Horário entrega", "value": pedido["horario_entrega"], "inline": False},
                    {"name": "Produto", "value": pedido["produto"], "inline": True},
                    {"name": "Quantidade", "value": str(pedido["quantidade"]), "inline": True},
                    {"name": "Valor total", "value": f"D$ {pedido['valor']}", "inline": True},
                    {"name": "Status", "value": "ENTREGUE", "inline": True},
                    {"name": "Criado em", "value": pedido["criado_em"], "inline": False},
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            enviar_webhook(WEBHOOK_VENDAS, embed=embed)

    conn.close()
    return redirect(url_for("pedidos"))

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
