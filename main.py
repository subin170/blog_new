from datetime import date
from functools import wraps
import os
from flask import Flask, abort, render_template, redirect, url_for, flash, jsonify, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm


'''
On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] =  os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Create a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database by user ID."""
    return db.session.get(User, int(user_id))


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] =  os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


def admin_only(func):
    """Decorator to restrict access to admin user only."""
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return func(*args, **kwargs)
    return decorated_view


def only_commenter(func):
    """Decorator to restrict access to comment author only."""
    @wraps(func)
    def decorated_view(**kwargs):
        if not current_user.is_authenticated:
            return abort(401)
        post_id, comment_id = kwargs['post_id'], kwargs['comment_id']
        # comment = Comment.query.get(comment_id)
        # if not comment:
        #     return abort(404)
        # above 3 lines are same is this line below,
        # If you want to do something custom before aborting use above else below
        comment = db.get_or_404(Comment, comment_id)

        if current_user.id != comment.author_id or comment.post_id != post_id:
            return abort(403)
        return func(**kwargs)
    return decorated_view


# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CONFIGURE TABLES

# Create a User table for all your registered users.
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

    #This will act like a List of BlogPost objects attached to each User
    posts = relationship("BlogPost",back_populates="author")
     #*******Add parent relationship to comment_class*******#
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # Create Foreign Key, "users.id" the users refers to the tablename of User
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to posts property in the User class.
    author = relationship("User", back_populates="posts")

    comments = relationship("Comment", back_populates="parent_post")

class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String(250), nullable=False)
     #*******Add child relationship*******#
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

with app.app_context():
    db.create_all()

# Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET","POST"])
def register():
    """Register a User"""
    form = RegisterForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email==form.email.data))
        user = result.scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        new_user = User(
            email = form.email.data,
            name = form.name.data,
            password = generate_password_hash(form.password.data, method='pbkdf2:sha256',
                                               salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form = form)


# Retrieve a user from the database based on their email.
@app.route('/login', methods=["GET","POST"])
def login():
    """Handle user login via form submission."""
    form = LoginForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email==form.email.data))
        user = result.scalar()
        if not user:
            flash("That email does not exist, Try another/ Register")
            return redirect(url_for('login'))
        if not check_password_hash(user.password, form.password.data):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('get_all_posts'))

    return render_template("login.html",form = form)


@app.route('/logout')
def logout():
    """Handle user logout"""
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    """Get all Posts."""
    page = request.args.get('page',1,type=int)
    per_page = 4
    posts = BlogPost.query.order_by(BlogPost.date.desc()).paginate(page=page, per_page=per_page)
    return render_template("index.html", all_posts=posts)
    # offset = (page - 1) * per_page
    # result = db.session.execute(db.select(BlogPost).order_by(BlogPost.date.desc()).
    #                             limit(per_page).offset(offset))
    # posts = result.scalars().all()
    # Get the total number of posts to calculate the total pages
    # total_posts = db.session.execute(db.select(db.func.count(BlogPost.id))).scalar()
    # Calculate the total number of pages
    # total_pages = (total_posts + per_page - 1) // per_page  # Using ceiling division
    # Render the template and pass the posts, current page, and total pages
    # return render_template('posts.html', posts=posts, page=page, total_pages=total_pages)


# Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET","POST"])
def show_post(post_id):
    """Show a particular post."""
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if form.validate_on_submit():
        new_comment = Comment(
            text = form.comment.data,
            comment_author = current_user,
            parent_post = requested_post
            )
        db.session.add(new_comment)
        db.session.commit()
        # Redirect after successful comment submission, else the comment you wrote in CKEditor field
        #  remains inside the editor after submitting(even though it's saved in the database)
        return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, form=form)


# Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    """Add new post."""
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    """Edit a post."""
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    """Delete a post."""
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route("/remove/<int:post_id>/<int:comment_id>")
@only_commenter
def delete_comment(post_id,comment_id):
    """Delete post's comment by its author"""
    comment_to_delete = db.get_or_404(Comment, comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post_id))

# Don't Use
@app.route('/delete/<int:user_id>', methods=["DELETE"])
def delete(user_id):
    """Delete User"""
    cafe = db.session.get(User, user_id)
    if cafe:
        db.session.delete(cafe)
        db.session.commit()
        return jsonify(success="Successfully deleted the user."), 200
    return jsonify(error={"Not Found": "Sorry user with that id not found in database."}), 404

@app.route("/about")
def about():
    """About Info"""
    return render_template("about.html")


@app.route("/contact")
def contact():
    """Contact details"""
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5001)
