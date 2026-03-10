from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'wverihdfuvuwi2482'


app.config['DATABASE'] = 'database.db'
app.config['COMPLAINT_UPLOAD_FOLDER'] = 'static/uploads/complaints'
os.makedirs(app.config['COMPLAINT_UPLOAD_FOLDER'], exist_ok=True)
app.config['PROFILE_UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'profiles')
os.makedirs(app.config['PROFILE_UPLOAD_FOLDER'], exist_ok=True)


def get_db_connection():
   
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                number TEXT,
                password TEXT NOT NULL,
                image_path TEXT,
                role TEXT DEFAULT 'user'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS complients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                image_path TEXT,
                result TEXT,
                user_email TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.close()

def allowed_file(filename, filetype):
    if filetype == 'image':
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    return False

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}


@app.route('/')
def index():
   
    return render_template('index.html',  title="Home")



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        number = request.form['number']
        password = request.form['password']
        profile_image = request.files['profile_image']
        role = request.form['role']

        filename = None
        if profile_image and allowed_file(profile_image.filename, 'image'):
            filename = secure_filename(profile_image.filename)
            image_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], filename)
            profile_image.save(image_path)
        else:
            flash('Invalid image file.', 'danger')
            return redirect(request.url)

        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (name, email, number, password, image_path, role) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, number, hashed_password, filename, role)
            )
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            conn.close()

    return render_template('register.html', title="Register")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
    
        if user and check_password_hash(user['password'], password):
            session['email'] = user['email']
            session['name'] = user['name']
            session['role'] = user['role']

            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'index'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html', title="Login")



@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html')



@app.route('/profile')
def profile():
    if 'email' not in session:
        flash('Please login to view your profile.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (session['email'],)).fetchone()
    conn.close()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)


@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    if 'email' not in session:
        flash('Please login to file a complaint.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        complaint_image = request.files.get('complaint_image')

        if not title or not description:
            flash('All fields are required.', 'danger')
            return redirect(request.url)

        filename = None
        if complaint_image and allowed_file(complaint_image.filename, 'image'):
            filename = secure_filename(complaint_image.filename)
            image_path = os.path.join(app.config['COMPLAINT_UPLOAD_FOLDER'], filename)
            complaint_image.save(image_path)
        else:
            flash('Please upload a valid image file.', 'danger')
            return redirect(request.url)

        conn = get_db_connection()
        conn.execute(
            '''
            INSERT INTO complients (title, description, image_path, user_email)

            VALUES (?, ?, ?, ?)
            ''',
            (title, description, filename, session['email'])
        )
        conn.commit()
        conn.close()

        flash('Complaint filed successfully.', 'success')
        return redirect(url_for('my_complaints'))

    return render_template('complaint.html', title="File Complaint")


@app.route('/my_complaints')
def my_complaints():
    if 'email' not in session:
        flash('Please login to view your complaints.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    complaints = conn.execute(
    "SELECT * FROM complients WHERE user_email = ?",
    (session['email'],)
).fetchall()

    conn.close()

    return render_template('my_complaints.html', complaints=complaints, title="My Complaints")


## Admin Routes
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    total_users = conn.execute("SELECT COUNT(*) FROM users ").fetchone()[0]
    
    total_complaints = conn.execute("SELECT COUNT(*) FROM complients").fetchone()[0]
    conn.close()

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_complaints=total_complaints,
                          
                           title="Admin Dashboard")


@app.route('/admin/users')
def admin_users():
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    return render_template('admin_users.html', users=users, title="Admin Users")


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()

   
    user = conn.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user or user['role'] in ('admin'):
        conn.close()
        flash('You cannot delete this user.', 'danger')
        return redirect(url_for('admin_users'))

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash('User deleted successfully.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/complaints')
def admin_complaints():
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    complaints = conn.execute("SELECT * FROM complients").fetchall()
    conn.close()

    return render_template('admin_complaints.html', complaints=complaints, title="Admin Complaints")

@app.route('/admin/complaint/edit/<int:complaint_id>', methods=['GET', 'POST'])
def admin_complaint_edit(complaint_id):
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    complaint = conn.execute("SELECT * FROM complients WHERE id = ?", (complaint_id,)).fetchone()

    if not complaint:
        conn.close()
        flash('Complaint not found.', 'danger')
        return redirect(url_for('admin_complaints'))

    if request.method == 'POST':
        result = request.form['result']
        status = request.form['status']

        conn.execute(
            "UPDATE complients SET result = ?, status = ? WHERE id = ?",
            (result, status, complaint_id)
        )
        conn.commit()
        conn.close()

        flash('Complaint updated successfully.', 'success')
        return redirect(url_for('admin_complaints'))

    conn.close()
    return render_template('admin_complaint_edit.html', complaint=complaint, title="Edit Complaint")


@app.route('/admin/complaint/delete/<int:complaint_id>', methods=['POST'])
def delete_complaint(complaint_id):
    if 'email' not in session or session.get('role') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute("DELETE FROM complients WHERE id = ?", (complaint_id,))
    conn.commit()
    conn.close()

    flash('Complaint deleted successfully.', 'success')
    return redirect(url_for('admin_complaints'))



@app.template_filter('time_ago')
def time_ago(value):
    """
    Converts datetime or datetime-string to 'x minutes ago'
    """
    if not value:
        return ''

  
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value 
    now = datetime.now()
    diff = now - value

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds // 60)} minutes ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} hours ago"
    elif seconds < 604800:
        return f"{int(seconds // 86400)} days ago"
    else:
        return value.strftime("%b %d, %Y")


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)