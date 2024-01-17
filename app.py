import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, check_password

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    rows = db.execute("SELECT username, stock_symbol, quantity, cash, current_price FROM stocks s JOIN users u ON s.user_id=u.id WHERE s.user_id=? ORDER BY stock_symbol;",session["user_id"])
    stock_total = 0

    # if the user has stocks
    if rows:
        # get the cash of the user
        cash = rows[0]["cash"]
        # if the user has stocks
        # for each stock
        for row in rows:
            # find the current price
            row["current_price"] = lookup(row["stock_symbol"])["price"]

            # add the total value of the stocks
            stock_total += row["current_price"] * row["quantity"]

        return render_template("index.html", rows=rows, username=rows[0]["username"], cash=cash, stock_total=stock_total)

    # if the user does not have stocks
    else:
        cash = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
        cash = cash[0]["cash"]
        username = db.execute("SELECT username FROM users WHERE id=?",session["user_id"])[0]["username"]
        return render_template("index.html", rows=rows, cash=cash, username=username, stock_total=0)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # if form was submitted
    if request.method == "POST":
        # get the symbol and amount of shares user will buy
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(symbol)

        if not shares.isnumeric() or not shares.isdecimal() or "-" in shares:
            return apology("Share quantity not correctly formatted. It must be a positive intger", 400)
        else:
            shares = int(shares)

        if not quote:
            return apology("Stock Not Found", 400)

        # validate user input
        if not symbol:
            return apology("Missing Stock Symbol", 400)
        if not shares or shares <= 0:
            return apology("Improper amount of shares", 400)

        # get user information to see if the user has enough money to buy
        user_data = db.execute("SELECT * FROM users WHERE id=?",session["user_id"])

        total_price = quote["price"] * shares
        balance_after = user_data[0]["cash"] - total_price

        if total_price > user_data[0]["cash"]:
            return apology("CANT AFFORD", 400)

        # get the time at this moment
        date = datetime.datetime.now()

        # update the transactions table in the db
        db.execute("INSERT INTO transactions (user_id, transaction_type, stock_symbol, stock_price, shares, total, balance_before, balance_after, timestamp_column) VALUES(?,?,?,?,?,?,?,?,?)",session["user_id"], "purchase", quote["symbol"], quote["price"], shares, total_price, user_data[0]["cash"], balance_after, date)

        # update the cash value in the user table
        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance_after, session["user_id"])

        #update the stocks page which contains the user data
        stocks = db.execute("SELECT * FROM stocks WHERE stock_symbol = ? and user_id = ?", quote["symbol"], session["user_id"])
        if stocks:
            db.execute("UPDATE stocks SET quantity=?", stocks[0]["quantity"] + shares)
        else:
            db.execute("INSERT INTO stocks (user_id, stock_symbol, quantity) VALUES (?,?,?)", session["user_id"], quote["symbol"], shares)

        flash("Purchase Completed")
        return redirect("/")

    # if method is get
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY timestamp_column", session["user_id"])
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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
    # if the method is post meaning the user sent the form
    if request.method == "POST":

        # get the sotck
        stock = request.form.get("symbol")

        # save the results of calling lookup
        results = lookup(stock)

        # check if lookup did not provided results
        if not results:
            return apology("Stock not found", 400)

        print(results)
        # if lookup does have results
        return render_template("quoted.html", price = usd(results["price"]), symbol= results["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # get the username and password
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # validate the user entered username and password
        if not username:
            return apology("Missing username", 400)

        elif not password:
            return apology("Missing password", 400)

        elif not check_password(password):
            return apology("Password does not meet complexity requirements", 400)

        elif  password != confirmation:
            return apology("Password do not match", 400)


        # check if the username already exists on the database
        users = db.execute("SELECT username FROM users")
        for user in users:
            if username in user["username"]:
                return apology("User already exists, choose another username", 400)

        # convert the password to a hash value
        hash = generate_password_hash(password, method='pbkdf2', salt_length=16)

        # if we get to this point we can add the new user to the database n
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        # get the id of the newly created user
        id = db.execute("SELECT id FROM USERS WHERE username=?", username)

        # log user in (by adding the user id to the session dict) and redirect them to the / route page
        session["user_id"] = id[0]["id"]
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        sell_stock = request.form.get("symbol")
        sell_shares = int(request.form.get("shares"))

        if not sell_stock:
            return apology("Missing Stock Symbol Field", 400)
        if not sell_stock:
            return apology("Missing Shares Field", 400)

        quote = lookup(sell_stock)

        # case stock is not found
        if not quote:
            return apology("Stock Not Found", 400)


        # query for the amount of stocks on the database
        avail_stocks = db.execute("SELECT quantity FROM stocks WHERE stock_symbol=?",sell_stock)[0]["quantity"]


        # if sufficient stocks to sell

        if avail_stocks >= sell_shares:
            # prepare values to register a new transaction
            date = datetime.datetime.now()
            total_price = sell_shares * quote["price"]
            user_data = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
            balance_after = user_data[0]["cash"] + total_price
            db.execute("INSERT INTO transactions (user_id, transaction_type, stock_symbol, stock_price, shares, total, balance_before, balance_after, timestamp_column) VALUES(?,?,?,?,?,?,?,?,?)",session["user_id"], "sell", quote["symbol"], quote["price"], sell_shares, total_price, user_data[0]["cash"], balance_after, date)

            # change the stocks database (amount of stocks)
            db.execute("UPDATE stocks SET quantity=? WHERE stock_symbol=?", avail_stocks - sell_shares, quote["symbol"])

            # change the user database (total chash)
            db.execute("UPDATE users SET cash=? WHERE id=?", balance_after, session["user_id"])

            # if we sold all the shares from a stock then drop the stock from the portfolio
            if avail_stocks == sell_shares:
                db.execute("DELETE FROM stocks WHERE stock_symbol=?",quote["symbol"])

            flash("Sell Transaction Completed")
            return redirect("/")
        else:
            return apology("NOT ENOUGH SHARES FOR TRANSACTION", 400)

    else:
        user_stocks = db.execute("SELECT * FROM stocks WHERE user_id=?",session["user_id"])
        return render_template("sell.html", user_stocks = user_stocks)


@app.route("/password_change", methods=["GET", "POST"])
@login_required
def password_change():
    if request.method == "POST":

        # get the previous password and the new with the confirmation
        previous_password = request.form.get("previous_password")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # print(previous_password)
        # print(db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"])
        # print(check_password_hash(db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"], previous_password))


        # if the old password does not match
        if not check_password_hash(db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])[0]["hash"], previous_password):
             return apology("Previous Password not correct. If you dont remember it contact admin", 400)

        # if the new password is missing
        elif not password:
            return apology("Missing password", 400)

        # if the new password does not meet requirements
        elif not check_password(password):
            return apology("Password does not meet complexity requirements", 400)

        # if the confirmation does not match
        elif  password != confirmation:
            return apology("Password do not match", 400)

        # if we got here everything is good

        # convert the password to a hash value
        hash = generate_password_hash(password, method='pbkdf2', salt_length=16)

        # store password on DB
        db.execute("UPDATE users SET hash=? WHERE id=?", hash, session["user_id"])

        flash("Password Changed")

        # redirect user to home page
        return redirect("/")

    else:
        return render_template("change_password.html")






