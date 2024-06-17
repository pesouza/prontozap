#!/usr/local/envs/flask/lib/python3.10
import datetime
import os
import stripe
from flask import Flask, flash
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for, jsonify

from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from flask_mail import Mail, Message
from time import time
import uuid

import config
if config.test:
    from mockdbhelper import MockDBHelper as DBHelper
else:
    from dbhelper import DBHelper

from passwordhelper import PasswordHelper
from bitlyhelper import BitlyHelper
from qrcodehelper import QrcodeHelper
from user import User

from forms import RegistrationForm
from forms import LoginForm
from forms import CreateTableForm
from forms import ContactForm


app = Flask(__name__)
app.secret_key = "Gxf613UhGRkzAKd47R5daLrUelnlUL4L6AU4z0uu++TNBpdzhAolufHqPQiiEdn34pbE97bmXbN"
login_manager = LoginManager(app)

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465 #587
app.config["MAIL_USE_TLS"] = False #True
app.config['MAIL_USE_SSL'] = True
app.config["MAIL_USERNAME"] = config.email
app.config["MAIL_PASSWORD"] = config.pwd

mail = Mail(app)

""" stripe_keys = {
    "secret_key": os.environ["STRIPE_SECRET_KEY"],
    "publishable_key": os.environ["STRIPE_PUBLISHABLE_KEY"],
}
"""
 
stripe_keys = {
    "secret_key": config.STRIPE_SECRET_KEY,
    "publishable_key": config.STRIPE_PUBLISHABLE_KEY,
    "price_id": config.STRIPE_PRICE_ID,
}

stripe.api_key = stripe_keys["secret_key"]

""" stripe.billing_portal.Configuration.create(
  business_profile={
    "headline": "Cactus Practice partners with Stripe for simplified billing.",
  },
  features={"invoice_history": {"enabled": True}},
) """

DB = DBHelper()
PH = PasswordHelper()
BH = BitlyHelper()
QH = QrcodeHelper()

YOUR_DOMAIN = 'https://waiterexpress.com.br'

def generate_confirmation_token():
    return str(uuid.uuid4().hex)

def send_confirmation_email(email, token):
    msg = Message(
        "Confirme seu endereço de e-mail",
        sender = ('Paulo Souza', config.email),
        recipients=[email],        
        html=render_template("confirm_email.html", 
                            confirm_url=f'{YOUR_DOMAIN}/confirm/{token}'),
    )
    mail.send(msg)

def send_contact_email(name, email, msg):
    msg = Message(
        f"Contado de {name}",
        sender = (name, email),
        recipients = [config.email],        
        body = msg
    )
    mail.send(msg)

def send_welcome_email(email, place):
    msg = Message(
        subject = 'Bem-vindo ao Waiter Express!',
        sender = ('Waiter Express', [config.email]),
        cc = [config.email],
        recipients = [email],        
        body = f"""
        Olá {place},

É com grande satisfação que recebemos você como novo usuário do Waiter Express! Sabemos o quanto é importante para o seu negócio ter um atendimento ágil e eficiente, por isso, estamos aqui para ajudar.

Com o Waiter Express, seus clientes poderão solicitar a presença do garçom de forma rápida e prática, usando apenas o celular, sem a necessidade de baixar nenhum aplicativo. Além disso, você poderá acompanhar em tempo real as solicitações e agilizar o atendimento de forma ainda mais eficiente.

Estamos comprometidos em oferecer um serviço de qualidade e estamos à disposição para esclarecer quaisquer dúvidas que possam surgir. Conte conosco para aprimorar o atendimento em seu estabelecimento e proporcionar uma experiência ainda mais satisfatória aos seus clientes.

Mais uma vez, seja muito bem-vindo ao Waiter Express!

Atenciosamente,
Equipe Waiter Express.
        """
    )
    mail.send(msg)

@login_manager.user_loader
def load_user(user_id):
    user_password = DB.get_user(user_id)
    if user_password:
        return User(user_id)


@app.route("/login", methods=["POST"])
def login():
    form = LoginForm(request.form)
    if form.validate():
        stored_user = DB.get_user(form.loginemail.data)
        if stored_user and PH.validate_password(form.loginpassword.data, stored_user['salt'], stored_user['hashed']) and stored_user['confirmed']:
            user = User(form.loginemail.data)
            login_user(user, remember=True)
            DB.last_login(stored_user["email"])
            return redirect(url_for('account'))
        form.loginemail.errors.append("E-mail ou senha inválido")
    return render_template("home.html", loginform=form, registrationform=RegistrationForm())


@app.route("/register", methods=["POST"])
def register():
    form = RegistrationForm(request.form)
    if form.validate():
        if DB.get_user(form.email.data):
            form.email.errors.append("Endereço de e-mail já registrado")
            return render_template("home.html", loginform=LoginForm(), registrationform=form)

        customer = stripe.Customer.create(
            email=request.form['email'],
            metadata={'estabelecimento': request.form['place']}
        )

        salt = PH.get_salt()
        hashed = PH.get_hash(form.password2.data + salt)
        token = generate_confirmation_token()
        DB.add_user(str(form.place.data), form.email.data, salt, hashed, token, customer.id)

        send_confirmation_email(form.email.data, token)

        return render_template("home.html", loginform=LoginForm(), registrationform=form, onloadmessage="Registro bem sucedido! Verifique sua caixa postal.")
    return render_template("home.html", loginform=LoginForm(), registrationform=form)

@app.route("/confirm/<token>")
def confirm_email(token):
    user = DB.confirm_email(token)
    if user is not None:
        send_welcome_email(user['email'], user['place'])
        return render_template("home.html", loginform=LoginForm(), registrationform=RegistrationForm(), onloadmessage="Seu email foi confirmado!")
        #return "Seu email foi confirmado!"
    else:
        #return render_template("home.html", loginform=LoginForm(), registrationform=RegistrationForm(), onloadmessage="Token inválido!")
        return "Token inválido!"

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/")
def home():
    testemunhos = DB.get_testem()
    return render_template("home.html", loginform=LoginForm(), registrationform=RegistrationForm(), 
                            testemunhos=testemunhos)


@app.route("/dashboard")
@login_required
def dashboard():
    now = datetime.datetime.now()
    requests = DB.get_requests(current_user.get_id())
    for req in requests:
        deltaseconds = (now - req['time']).seconds
        req['wait_minutes'] = "{}.{}".format((deltaseconds//60), str(deltaseconds % 60).zfill(2))
    return render_template("dashboard.html", requests=requests)


@app.route("/dashboard/resolve")
@login_required
def dashboard_resolve():
    request_id = request.args.get("request_id")
    DB.delete_request(request_id)
    return redirect(url_for('dashboard'))


@app.route("/account")
@login_required
def account():
    tables = DB.get_tables(current_user.get_id())
    user = DB.get_user(current_user.email)
    return render_template("account.html", 
                            createtableform=CreateTableForm(), 
                            tables=tables,
                            user = user)


@app.route("/account/createtable", methods=["POST"])
@login_required
def account_createtable():
    form = CreateTableForm(request.form)
    if form.validate():
        tableid = DB.add_table(form.tablenumber.data, current_user.get_id())
        long_url = f'{config.base_url}/newrequest/{tableid}'
        new_url = BH.shorten_url(long_url)
        new_qrc = QH.gen_code(form.tablenumber.data, new_url, long_url, tableid)
        if new_url is None:
            new_url = long_url
        DB.update_table(tableid, new_url, new_qrc)
        return redirect(url_for('account'))
    return render_template("account.html", createtableform=form, tables=DB.get_tables(current_user.get_id()))


@app.route("/account/deletetable")
@login_required
def account_deletetable():
    tableid = request.args.get("tableid")
    DB.delete_table(tableid)
    return redirect(url_for('account'))


@app.route("/newrequest/<tid>")
def new_request(tid):
    if DB.add_request(tid, datetime.datetime.now()):
        message = "Seu garçom está a caminho!"
        background_color = "green"
        sound = 'sounds/ok.wav'
        image = 'site/ok.png'
    else:
        message = "Por favor, seja paciente. Você será atendido o mais rápido possível!"
        background_color = "red"
        sound = 'sounds/again.wav'
        image = 'site/again.png'

    return render_template("request.html", message=message, 
                            background_color=background_color,
                            sound=sound, image=image)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm(request.form)
    if form.validate():

        send_contact_email(form.name.data, form.email.data, form.message.data)

        return render_template("contact.html", form=ContactForm(), 
                                onloadmessage="Agradecemos o seu contato. Responderemos ASAP.")
    return render_template("contact.html", form=ContactForm(request.form))

@app.route("/privacidade")
def privacidade():
    return render_template("privacidade.html")

@app.route("/termos")
def termos():
    return render_template("termos.html")

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        prices = stripe.Price.list(
            lookup_keys=[request.form['lookup_key']],
            expand=['data.product']
        )

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': prices.data[0].id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            customer=request.form['customer'],
            success_url=YOUR_DOMAIN +
            '/success.html?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + '/cancel.html',
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(e)
        return f"Server error: {e}", 500

@app.route('/create-portal-session', methods=['POST'])
@login_required
def customer_portal():
    # For demonstration purposes, we're using the Checkout session to retrieve the customer ID.
    # Typically this is stored alongside the authenticated user in your database.
    checkout_session_id = request.form.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    # This is the URL to which the customer will be redirected after they are
    # done managing their billing with the portal.
    return_url = YOUR_DOMAIN

    portalSession = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=return_url,
    )
    return redirect(portalSession.url, code=303)

@app.route('/webhook', methods=['POST'])
def webhook_received():
    # Replace this endpoint secret with your endpoint's unique secret
    # If you are testing with the CLI, find the secret by running 'stripe listen'
    # If you are using an endpoint defined with the API or dashboard, look in your webhook settings
    # at https://dashboard.stripe.com/webhooks
    webhook_secret = 'whsec_12345'
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    print('event ' + event_type)

    if event_type == 'checkout.session.completed':
        print('🔔 Payment succeeded!')
    elif event_type == 'customer.subscription.trial_will_end':
        print('Subscription trial will end')
    elif event_type == 'customer.subscription.created':
        print('Subscription created %s', event.id)
    elif event_type == 'customer.subscription.updated':
        print('Subscription created %s', event.id)
    elif event_type == 'customer.subscription.deleted':
        # handle subscription canceled automatically based
        # upon your subscription settings. Or if the user cancels it.
        print('Subscription canceled: %s', event.id)

    return jsonify({'status': 'success'})

@app.route('/adicionar_testemunho', methods=['GET', 'POST'])
@login_required
def adicionar_testemunho():
    if request.method == 'POST':
        nome = request.form['nome']
        estabelecimento = request.form['estabelecimento']
        depoimento = request.form['depoimento']
        DB.add_testem(nome=nome, estabelecimento=estabelecimento, depoimento=depoimento)
        flash('Testemunho adicionado com sucesso!')
        return redirect(url_for('home'))
    return render_template('adicionar_testemunho.html')


if __name__ == '__main__':
    app.run()
