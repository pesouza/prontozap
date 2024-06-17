from flask import Flask, request, jsonify, render_template, flash, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import csv
import os
import hashlib
import time
import webbrowser as web
from datetime import datetime
import pyautogui as pg

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)

# Função para enviar mensagem via WhatsApp
def enviar_mensagem_whatsapp(numero_telefone, mensagem):
    web.open("https://wa.me/55" + numero_telefone + "?text=" + mensagem)
    time.sleep(10)
    width, height = pg.size()
    pg.click(2 * width // 3, 2 * height // 3)
    time.sleep(5)
    pg.press('enter')
    time.sleep(5)
    pg.press('enter')

# Funções relacionadas a usuários
def verificar_arquivo_csv(filename, fields):
    if not os.path.exists(filename):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(fields)

def carregar_usuarios():
    verificar_arquivo_csv('users.csv', ['username', 'password'])
    usuarios = []
    with open('users.csv', 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            usuarios.append(row)
    return usuarios

def usuario_existe(username):
    usuarios = carregar_usuarios()
    return any(usuario['username'] == username for usuario in usuarios)

def cadastrar_usuario(username, password):
    usuarios = carregar_usuarios()
    if not usuario_existe(username):
        with open('users.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([username, hashlib.sha256(password.encode()).hexdigest()])
        return True
    return False

def verificar_credenciais(username, password):
    usuarios = carregar_usuarios()
    for usuario in usuarios:
        if usuario['username'] == username and usuario['password'] == hashlib.sha256(password.encode()).hexdigest():
            return True
    return False

# Funções relacionadas a pedidos
def verificar_arquivo_pedidos():
    if not os.path.exists('pedidos.csv'):
        with open('pedidos.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Nome', 'Telefone', 'Data', 'Hora', 'QR Code', 'Numero do Pedido', 'Status'])

def carregar_pedidos():
    verificar_arquivo_pedidos()
    numero_pedido = '1'
    pedidos_por_data = {}
    with open('pedidos.csv', 'r', newline='') as file:
        reader = csv.DictReader(file)
        reader = sorted(reader, key=lambda row: (row['Data'], int(row['Numero do Pedido'])))
        for row in reader:
            data_pedido = row['Data']
            if data_pedido not in pedidos_por_data:
                pedidos_por_data[data_pedido] = []
            pedidos_por_data[data_pedido].append(row)
            numero_pedido = str(int(row['Numero do Pedido']) + 1)
    return pedidos_por_data, numero_pedido

def atualizar_status_pedido(numero_pedido, novo_status):
    linhas = []
    with open('pedidos.csv', 'r', newline='') as file:
        reader = csv.reader(file)
        for row in reader:
            if row[5] == numero_pedido:  # Verificar se é o pedido correto
                row[-1] = novo_status  # Atualizar o status do pedido
            linhas.append(row)
    with open('pedidos.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(linhas)

# Rotas relacionadas a autenticação e cadastro de usuários
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verificar_credenciais(username, password):
            session['logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect('/dashboard')
        else:
            flash('Usuário ou senha incorretos.', 'error')
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Você foi desconectado.', 'info')
    return render_template('index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if cadastrar_usuario(username, password):
            flash('Cadastro realizado com sucesso! Faça login para acessar sua conta.', 'success')
            return render_template('index.html')
        else:
            flash('Este usuário já existe. Por favor, escolha outro nome de usuário.', 'error')
    return render_template('cadastro.html')

# Rotas relacionadas ao dashboard e pedidos
@app.route('/dashboard')
def dashboard():
    if 'logged_in' in session:
        pedidos_por_data, _ = carregar_pedidos()
        return render_template('dashboard.html', pedidos_por_data=pedidos_por_data)
    else:
        flash('Você precisa fazer login para acessar esta página.', 'error')
        return render_template('index.html')

@app.route('/dashboard', methods=['POST'])
def filtrar_pedidos():
    data_filtro = request.form.get('data-filter')
    data_filtro = datetime.strptime(data_filtro, '%Y-%m-%d').strftime("%d/%m/%Y")
    
    status_filtro = request.form.get('status-filter')
    pedidos_filtrados = {}

    if not data_filtro and not status_filtro:
        return redirect('/')
    else:
        # Aplicar filtros
        with open('pedidos.csv', 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if (not data_filtro or row['Data'] == data_filtro) and (not status_filtro or row['Status'] == status_filtro):
                    data_pedido = row['Data']
                    if data_pedido not in pedidos_filtrados:
                        pedidos_filtrados[data_pedido] = []
                    pedidos_filtrados[data_pedido].append(row)

    return render_template('dashboard.html', pedidos_por_data=pedidos_filtrados)

@app.route('/gerar_qr', methods=['POST'])
def gerar_qr():
    try:
        order_details = request.json
        order_details['data'] = datetime.now().strftime("%d/%m/%Y")
        order_details['hora'] = datetime.now().strftime("%H:%M:%S")
        _, numero_pedido = carregar_pedidos()
        order_details['Numero do Pedido'] = numero_pedido
        order_details['QR Code'] = ''
        with open('pedidos.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([order_details['nome'], order_details['telefone'], 
                             order_details['data'], order_details['hora'], 
                             order_details['QR Code'], int(numero_pedido), 'Em andamento'])
        mensagem = f'Olá {order_details["nome"]}%0APedido recebido às {order_details["hora"]}%0ANúmero do Pedido: {numero_pedido}'
        enviar_mensagem_whatsapp(order_details['telefone'], mensagem)
        return jsonify({'order_details': order_details}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/atualizar_status', methods=['POST'])
def atualizar_status():
    try:
        numero_pedido = request.form.get('numero_pedido')
        novo_status = request.form.get('novo_status')
        telefone = request.form.get('telefone')
        atualizar_status_pedido(numero_pedido, novo_status)
        mensagem = f'Pedido Número: {numero_pedido}%0A{novo_status}'
        enviar_mensagem_whatsapp(telefone, mensagem)
        time.sleep(5)
        return redirect('/dashboard')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/excluir_pedido', methods=['POST'])
def excluir_pedido():
    try:
        numero_pedido = request.form.get('numero_pedido')
        linhas = []
        with open('pedidos.csv', 'r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[5] != numero_pedido:
                    linhas.append(row)
        with open('pedidos.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(linhas)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Rota para a landpage
@app.route('/')
def landpage():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
