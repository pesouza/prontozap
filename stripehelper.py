from flask import Flask, redirect, url_for, request, render_template
import stripe

app = Flask(__name__)

stripe.api_key = "YOUR_STRIPE_API_KEY"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/pay", methods=["POST"])
def pay():
    customer = stripe.Customer.create(email=request.form["stripeEmail"],
                                      source=request.form["stripeToken"])

    stripe.Subscription.create(customer=customer.id,
                               items=[{ "plan": "monthly_plan" }])

    return redirect(url_for("success"))

@app.route("/success")
def success():
    return "Obrigado por se tornar um assinante!"

if __name__ == "__main__":
    app.run(debug=True)
