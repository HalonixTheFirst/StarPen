import os
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from helper import login_required
from flask_sqlalchemy import SQLAlchemy



app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql://username:password@localhost:5432/blogdb"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    hash = db.Column(db.String(200), nullable=False)
    blogs=db.relationship("Blog",backref="author",lazy=True)

class Blog(db.Model):
    __tablename__ = "blogs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("login.html", error="Missing credentials")

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.hash, password):
            return render_template("login.html", error="Invalid Username or Password")

        session["user_id"] = user.id
        return redirect("/")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return render_template("register.html", error="Please provide a username")

        if password != confirmation:
            return render_template("register.html", error="Passwords do not match")

        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already taken")

        pw_hash = generate_password_hash(password)
        user = User(username=username, hash=pw_hash)

        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")

@app.route("/")
@login_required
def index():
    if "user_id" not in session:
        return render_template("home.html")

    user = User.query.get(session["user_id"])
    return render_template("index.html", name=user.username)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
