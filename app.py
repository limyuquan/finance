import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT * FROM user_portfolio WHERE user_id = ? ORDER BY name ASC", session["user_id"])
    total_sum_stocks = 0
    for dictionary in stocks:
        stock = lookup(dictionary["symbol"])
        price = stock["price"]
        dictionary["price"] = usd(price)
        dictionary["total_price"] = usd(price * dictionary["quantity"])
        total_sum_stocks += price * dictionary["quantity"]

    funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    total_sum = usd(funds + total_sum_stocks)
    return render_template("index.html", stocks=stocks, total_sum=total_sum, funds=usd(funds),total_sum_stocks=usd(total_sum_stocks))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quantity = request.form.get("shares")
        if not symbol:
            return apology("Please input Symbol")
        if not quantity:
            return apology("Please input Quantity")
        try:
            if int(quantity)<= 0:
                return apology("Please input Valid Quantity")
        except:
            return apology("Please input valid Quantity")

        if lookup(symbol) == None:
            return apology("symbol is wrong")
        stock = lookup(symbol)
        stock_name=stock["name"]
        stock_price=stock["price"]
        symbol = symbol.strip()

        funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        if funds:
            #if there are not enough funds
            if funds < (stock_price * int(quantity)):
                return apology("Not enough funds")
            #if there are enough funds proceed with buying stock
            #add stock into the transactions table
            db.execute("INSERT INTO transactions (transaction_type, user_id, name, symbol, quantity, price, datetime) VALUES (?,?,?,?,?,?,?)", "buy", session["user_id"],stock_name, symbol, quantity, stock_price, datetime.now())
            #deduct money from the users DB
            cash_after_buy = funds - (stock_price * int(quantity))
            db.execute("UPDATE users SET cash = ? WHERE id = ? ", cash_after_buy, session["user_id"])
            rows = db.execute("SELECT * FROM user_portfolio WHERE user_id = ? AND symbol = ?",session["user_id"], symbol)
            #stock not previously in user's portfolio
            if len(rows) == 0:
                db.execute("INSERT INTO user_portfolio (user_id, name, symbol, quantity) VALUES (?,?,?,?)", session["user_id"],stock_name, symbol, quantity,)
            #stock previously in user's portfolio
            elif len(rows) == 1:
                prev_quantity = rows[0]["quantity"]
                print(type(prev_quantity))
                db.execute("UPDATE user_portfolio SET quantity = ? WHERE user_id = ? AND symbol = ?", (prev_quantity + int(quantity)), session["user_id"],symbol)

            return redirect("/")

        # if cannot find funds
        else:
            return apology("funds dont exist")

    return apology("Error in buying")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    """Show history of transactions"""
    if (request.method == "POST" and request.form.get("all")) or (request.method == "GET"):
        rows = db.execute("SELECT * FROM transactions WHERE user_id = ? ", session["user_id"])

    elif request.method == "POST":
        if request.form.get("buy"):
            buy_sell = "buy"
        if request.form.get("sell"):
            buy_sell = "sell"
        rows = db.execute("SELECT * FROM transactions WHERE user_id = ? AND transaction_type = ?", session["user_id"], buy_sell)



    return render_template("history.html", rows=rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            print("symbol wrong")
            return apology("symbol is wrong")
        stock = lookup(symbol)
        return render_template("quoted.html", name=stock["name"], price=usd(stock["price"]), symbol=stock["symbol"] )


    print("failure")
    return apology("todo quote")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
         # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("please repeat password", 400)

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if password != confirmation:
            return apology("passwords not the same", 400)

        if len(db.execute("SELECT * FROM users WHERE username = ?", username)) != 0:
            return apology("username exists", 400)

        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username,hash) VALUES (?,?)", username, password_hash)
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]

        return redirect("/")

    return render_template("register.html")

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not request.form.get("cur_password"):
            return apology("must provide current password", 400)
        actual_cur_hash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"]

        if not check_password_hash(actual_cur_hash, request.form.get("cur_password")):
            return apology("Current Password incorrect", 400)
        if not request.form.get("password"):
            return apology("must provide password", 400)
        if not request.form.get("confirmation"):
            return apology("please repeat password", 400)
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if password != confirmation:
            return apology("passwords not the same", 400)
        password_hash = generate_password_hash(password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", password_hash, session["user_id"])
        return apology("Password Changed Successfully")


    return render_template("change_password.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        qty_request = request.form.get("shares")
        if not request.form.get("symbol"):
            return apology("Please select Symbol")
        if not request.form.get("shares"):
            return apology("Please select Quantity")
        symbol = request.form.get("symbol").strip()
        qty_request = int(request.form.get("shares"))
        qty_avail = db.execute("SELECT quantity FROM user_portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)[0]["quantity"]
        if qty_avail == 0:
            return apology("You do not have any stock")
        if qty_avail < qty_request:
            return apology("You do not have enough stock")
        #all verified
        #update the transaction table
        stock = lookup(symbol)
        stock_name=stock["name"]
        stock_price=stock["price"]
        funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        db.execute("INSERT INTO transactions (transaction_type, user_id, name, symbol, quantity, price, datetime) VALUES (?,?,?,?,?,?,?)", "sell", session["user_id"],stock_name, symbol, qty_request, stock_price, datetime.now())
        #update my cash
        cash_after_sell = funds + (stock_price * qty_request)
        db.execute("UPDATE users SET cash = ? WHERE id = ? ", cash_after_sell, session["user_id"])
        #update my portfolio
        rows = db.execute("SELECT * FROM user_portfolio WHERE user_id = ? AND symbol = ?",session["user_id"], symbol)
        if len(rows) == 1:
            cur_qty = qty_avail - qty_request
            #if stock count in 0 in portfolio, remove stock from table
            if cur_qty == 0:
                db.execute("DELETE FROM user_portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
            else:
                db.execute("UPDATE user_portfolio SET quantity = ? WHERE user_id = ? AND symbol = ? ", cur_qty, session["user_id"], symbol)

        return redirect("/")

    else:
        rows = db.execute("SELECT * FROM user_portfolio WHERE user_id = ?", session["user_id"])
        print(rows)
        return render_template("sell.html", rows=rows)

@app.route("/funds", methods=["GET", "POST"])
@login_required
def funds():
    if request.method == "POST":
        if not request.form.get("funds"):
            return apology("Please Add funds")
        add_funds = int(request.form.get("funds"))
        cur_funds = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cur_funds+add_funds, session["user_id"])
        return apology("funds added")
    return render_template("funds.html")


