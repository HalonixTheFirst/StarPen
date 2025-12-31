import os
import uuid
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

from helper import login_required

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = 'static/uploads/thumbnails'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)



class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    hash = db.Column(db.String(200), nullable=False)
    blogs = db.relationship("Blog", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True, cascade="all, delete-orphan")


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    blogs = db.relationship("Blog", backref="category", lazy=True)


class Blog(db.Model):
    __tablename__ = "blogs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    comments = db.relationship(  "Comment",backref="blog",lazy=True,cascade="all, delete-orphan")



class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey("blogs.id"), nullable=False)



@app.route("/")
@login_required
def index():
    user = User.query.get(session["user_id"])
    search_query = request.args.get('q')

    if search_query:
        # We join with User to access the username column for the filter
        blogs = Blog.query.join(User).filter(
            (Blog.title.ilike(f'%{search_query}%')) |
            (Blog.content.ilike(f'%{search_query}%')) |
            (User.username.ilike(f'%{search_query}%')) # Search by author name
        ).order_by(Blog.created_at.desc()).all()
    else:
        blogs = Blog.query.order_by(Blog.created_at.desc()).all()
    return render_template("index.html", user=user, blogs=blogs, search_query=search_query)

@app.route("/blog/<int:blog_id>/comment", methods=["POST"])
@login_required
def add_comment(blog_id):
    content = request.form.get("comment_content")
    if not content or content.strip() == "":
        return redirect(url_for('blog', id=blog_id))

    comment = Comment(
        content=content,
        user_id=session["user_id"],
        blog_id=blog_id
    )
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('blog', id=blog_id))


@app.route("/comment/delete/<int:comment_id>", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    blog_id = comment.blog_id

    # Check if user is the owner of the comment
    if comment.user_id == session["user_id"]:
        db.session.delete(comment)
        db.session.commit()

    return redirect(url_for('blog', id=blog_id))


@app.route("/blog/<int:id>")
def blog(id):
    blog = Blog.query.get_or_404(id)
    # Sort comments by date descending manually or via query
    comments = Comment.query.filter_by(blog_id=id).order_by(Comment.created_at.desc()).all()
    return render_template("blog.html", blog=blog, comments=comments)


@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        category_id = request.form.get("category")
        file = request.files.get("thumbnail")

        if not title or not content or not category_id:
            return render_template(
                "create.html",
                error="All fields are required",
                categories=categories
            )

        filename = None
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        blog = Blog(
            title=title,
            content=content,
            user_id=session["user_id"],
            thumbnail=filename,
            category_id=category_id
        )

        db.session.add(blog)
        db.session.commit()
        return redirect("/")

    return render_template("create.html", categories=categories)



@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    blog = Blog.query.get_or_404(id)
    if blog.user_id != session["user_id"]:
        return redirect("/")

    if request.method == "POST":
        blog.title = request.form.get("title")
        blog.content = request.form.get("content")
        blog.category_id = request.form.get("category")

        if request.form.get("remove_image") == "true" and blog.thumbnail:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], blog.thumbnail))
            except:
                pass
            blog.thumbnail = None

        file = request.files.get("thumbnail")
        if file and file.filename != '':
            if blog.thumbnail:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], blog.thumbnail))
                except:
                    pass
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            blog.thumbnail = filename

        db.session.commit()
        return redirect("/my-blogs")
    categories = Category.query.order_by(Category.name).all()
    return render_template("edit.html", blog=blog, categories=categories)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    blog = Blog.query.get_or_404(id)
    if blog.user_id == session["user_id"]:
        if blog.thumbnail:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], blog.thumbnail))
            except:
                pass
        db.session.delete(blog)
        db.session.commit()
    return redirect("/my-blogs")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if not username or not password:
            return render_template("login.html", error="Missing credentials", preview_blogs=Blog.query.limit(3).all())
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.hash, password):
            return render_template("login.html", error="Invalid Username or Password",
                                   preview_blogs=Blog.query.limit(3).all())
        session["user_id"] = user.id
        return redirect("/")
    return render_template("login.html", preview_blogs=Blog.query.order_by(Blog.created_at.desc()).limit(3).all())


@app.route("/register", methods=["GET", "POST"])
def register():
    def get_previews():
        return Blog.query.order_by(Blog.created_at.desc()).limit(3).all()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username or not password:
            return render_template("register.html", error="All fields are required", preview_blogs=get_previews())
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters",
                                   preview_blogs=get_previews())
        if password != confirmation:
            return render_template("register.html", error="Passwords do not match", preview_blogs=get_previews())
        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="Username already taken", preview_blogs=get_previews())
        new_user = User(username=username, hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html", preview_blogs=get_previews())

@app.route("/my-blogs")
@login_required
def my_blogs():
    blogs = Blog.query.filter_by(user_id=session["user_id"]).order_by(Blog.created_at.desc()).all()
    return render_template("my-blogs.html", blogs=blogs)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if Category.query.count() == 0:
            db.session.add_all([
                Category(name="Technology"),
                Category(name="Education"),
                Category(name="Entertainment"),
                Category(name="News"),
                Category(name="Opinion"),
                Category(name="Health"),
                Category(name="Food"),
                Category(name="Travel"),
                Category(name="Business"),
            ])
            db.session.commit()

    app.run(debug=True)
