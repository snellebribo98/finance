# Problem set 8
# Name: Brian van de Velde
# Student ID: 12476390
# Time: 48:00
#
# Problem finance is een website waarin je aandelen kan opzoeken, kopen,
# verkopen, transactie geschiedenis kan bekijken en extra geld kan storten
# om meer aandelen te kunnen kopen.


import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def after_request(response):
    # Ensure responses aren't cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Load the portofolio
    id = session["user_id"]
    owned = db.execute("SELECT * FROM portofolio WHERE id = :id", id=id)
    total_stock_cash = 0

    # for each row of shares you have the needed information is retrieved
    for row in owned:
        id = session["user_id"]
        symbol = row["symbol"]
        shares = row["shares"]
        stock = lookup(row["symbol"])
        price = stock["price"]
        cost = round(float(shares * price), 2)
        total_stock_cash += cost

        # update the portofolio with the new price, cost
        db.execute("UPDATE portofolio SET price = :price, cost = :cost \
                   WHERE id = :id AND symbol = :symbol",
                   price=usd(price), cost=usd(cost), id=id, symbol=symbol)

    # takes the cash of that user to calculate the grand total
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=id)
    cash = cash[0]["cash"]
    cash = round(float(cash), 2)
    total_cash = round(float(cash + total_stock_cash), 2)
    owned = db.execute("SELECT * FROM portofolio WHERE id = :id", id=id)
    return render_template("index.html", owned=owned, cash=usd(cash),
                           grand_total=usd(total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via GET, returned to buy page
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Checks if symbol is valid
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid symbol", 400)

        # Checks if user inputs a value
        if not request.form.get("shares").isdigit():
            return apology("must provide positive value", 400)

        # Rounds of shares and makes price a two decimal number
        # Checks if given value of shares is positive
        id = session["user_id"]
        symbol = stock["symbol"]
        price = round(float(stock["price"]), 2)
        shares = int(request.form.get("shares"))
        stock_name = stock["name"]
        if shares < 1:
            return apology("must provide a positive number of shares")

        # Compare the cash of the user against the cost of the shares
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=id)
        cost = round(float(shares * price), 2)
        if cost > cash[0]["cash"]:
            return apology("Insufficient cash", 403)

        else:
            # Execute the transactions
            db.execute("INSERT INTO transactions (id,symbol,shares,price,cost)\
                       VALUES (:id,:symbol,:shares,:price, :cost);",
                       id=id, symbol=stock["symbol"], shares=shares,
                       price=price, cost=cost)

            # Update cash of user
            db.execute("UPDATE users SET cash = cash -:cost WHERE id = :id",
                       cost=cost, id=id)

            # Update the portofolio with you transactions
            update = 0
            transaction_symbol = request.form.get("symbol")
            portofolio_symbol = db.execute("SELECT symbol FROM portofolio \
                                           WHERE id = :id", id=id)

            # Find the symbol in the transaction
            for row in portofolio_symbol:
                if row["symbol"] == transaction_symbol:
                    update = 1
                    break

            # If transaction symbol not in portofolio add it
            if update == 1:
                db.execute("UPDATE portofolio SET shares = shares + :shares,\
                           price = price + :price, cost = cost + :cost WHERE \
                           id = :id AND symbol = :symbol", id=id,
                           shares=shares, price=price, cost=cost,
                           symbol=symbol)

            # If transaction symbol already in portofolio update it
            else:
                db.execute("INSERT INTO portofolio(id, stock_name, shares, price,\
                           cost,symbol) VALUES (:id,:stock_name,:shares,\
                           :price,:cost,:symbol);", id=id,
                           stock_name=stock_name, symbol=symbol,
                           shares=shares, price=price, cost=cost)

            # update history
            db.execute("INSERT INTO histories (id, symbol, shares, price, \
                       cost) VALUES(:id, :symbol, :shares, :price, :cost)",
                       id=id, symbol=symbol, shares=shares, price=usd(price),
                       cost=usd(cost))

        # Message if you succesfully bought shares
        flash('You succesfully bought shares!')
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # picks the date of the transaction
    date = datetime.datetime.now()
    id = session["user_id"]

    histories = db.execute("SELECT * FROM histories WHERE id = :id", id=id)

    return render_template("history.html", histories=histories, date=date)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via GET, returned to buy page
    if request.method == "GET":
        return render_template("login.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        check_password = check_password_hash(rows[0]["hash"],
                                             request.form.get("password"))
        if len(rows) != 1 or not check_password:
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")


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

    # User reached route via GET, returned to quote page
    if request.method == "GET":
        return render_template("quote.html")

    # User reached route via POST and checks whether given symbol is valid
    if request.method == "POST":

        # Looks up the quote symbol
        quote = lookup(request.form.get("symbol"))

        # If quote is not recognized
        if not quote:
            return apology("Stock not found", 400)

        # Looks up the quote price
        quote_price = usd(quote["price"])

        return render_template("quoted.html", quote=quote,
                               quote_price=quote_price)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via GET, returned to register page
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure password and confirmation are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("must provide the same password twice", 400)

        username = request.form.get("username")
        hashed = generate_password_hash(request.form.get("password"))

        # Store the hash or password
        result = db.execute("INSERT INTO users (username, hash) \
                            VALUES(:username, :hash)",
                            username=username, hash=hashed)

        # If username is already taken
        if not result:
            return apology("must be a new username")

        # remeber who logged in after being registered
        session["user_id"] = result

        # Message after succesfully registering
        flash("You are registered!")

        # Redirect user to home page
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via GET, returned to buy page
    if request.method == "GET":

        # List of symbols you can sell
        id = session["user_id"]
        names = []
        portofolio_symbol = db.execute("SELECT symbol FROM portofolio WHERE \
                                       id = :id", id=id)

        # each symbol the user has is appended into a list of names
        for row in portofolio_symbol:
            names.append(row["symbol"])

        return render_template("sell.html", names=names)

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Checks if symbol is valid
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol", 400)

        # Checks if user inputs a value
        if not request.form.get("shares").isdigit():
            return apology("must provide positive value")

        # Rounds of shares and makes price a two decimal number
        # Checks if given value of shares is positive
        id = session["user_id"]
        symbol = stock["symbol"]
        shares = int(request.form.get("shares"))
        price = stock["price"]
        cost = stock["price"] * float(shares)
        stock_name = stock["name"]
        if shares < 1:
            return apology("must provide a positive number of shares", 403)

        # Compare the cash of the user against the cost of the shares
        amount = db.execute("SELECT shares FROM portofolio WHERE id = :id AND \
                            symbol = :symbol", id=id, symbol=symbol)
        amount = amount[0]["shares"]

        # if the user selects more shares than the user has
        if shares > int(amount):
            return apology("Insufficient shares", 400)

        else:

            # Update cash of user
            db.execute("UPDATE users SET cash = cash + :purchase WHERE \
                       id = :id", id=id, purchase=cost)

            # new amount of shares
            total_shares = amount - shares

            # if all shares of symbol are sold delete it from portofolio
            if total_shares < 1:
                db.execute("DELETE FROM portofolio WHERE id=:id AND \
                           symbol=:symbol", id=id, symbol=symbol)

            # else update portofolio
            else:
                db.execute("UPDATE portofolio SET shares =:shares WHERE \
                           id = :id AND symbol = :symbol",
                           shares=total_shares, id=id, symbol=symbol)

            # update history
            db.execute("INSERT INTO histories (id, symbol, shares, price, \
                       cost) VALUES(:id, :symbol, :shares, :price, :cost)",
                       id=id, symbol=symbol, shares=-shares, price=usd(price),
                       cost=usd(cost))

        # Message if you succesfully bought shares
        flash('You succesfully sold shares!')
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit money."""

    # User reached route via GET, returned to deposit page
    if request.method == "GET":
        return render_template("deposit.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Checks if valid input
        if not request.form.get("amount"):
            return apology("must provide deposit value", 400)

        # Checks if user inputs a value
        if not request.form.get("amount").isdigit():
            return apology("must provide positive value")

        # Checks if given value of shares is positive
        id = session["user_id"]
        amount = int(request.form.get("amount"))
        if amount < 1:
            return apology("must provide a positive deposit", 403)

        # Update cash of user
        db.execute("UPDATE users SET cash = cash + :purchase WHERE id = :id",
                   id=id, purchase=amount)

    # Message if you succesfully bought shares
    flash('You succesfully deposited money!')
    return redirect("/")


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
