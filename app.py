from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import mysql.connector
from admin_routes import admin_bp
from petugas_routes import petugas_bp

app = Flask(__name__)
app.secret_key = 'web_caleg'

# Registrasi Blueprint
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(petugas_bp, url_prefix='/petugas')

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_caleg_jaktim_tibi"
    )

# --- TAMBAHAN: Agar halaman tidak bisa diakses via tombol 'Back' setelah logout ---
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/', methods=['GET', 'POST'])
def login():
    # Jika sudah login, jangan kasih akses ke halaman login lagi, lempar ke dashboard
    if session.get('logged_in'):
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('petugas.dashboard_petugas'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            
            # 1. Cek Admin
            cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password))
            user_admin = cursor.fetchone()
            
            if user_admin:
                session['logged_in'] = True
                session['user_id'] = user_admin['id_admin']
                session['role'] = 'admin'
                session['nama'] = user_admin['nama_admin']
                return redirect(url_for('admin.dashboard'))
                
            # 2. Cek Relawan
            cursor.execute("SELECT * FROM relawan WHERE username = %s AND password = %s", (username, password))
            user_relawan = cursor.fetchone()
            
            # Di dalam app.py bagian login relawan
            if user_relawan:
                session['logged_in'] = True
                session['user_id'] = user_relawan['id_relawan']
                session['id_user'] = user_relawan['id_relawan'] # Sinkronkan nama variabel ID
                session['nama'] = user_relawan['nama_relawan']
                session['role'] = 'petugas'
                
                # PASTIKAN NAMA KOLOM DI DATABASE ADALAH 'id_kecamatan'
                session['id_kecamatan'] = user_relawan['id_kecamatan'] 
                
                return redirect(url_for('petugas.dashboard_petugas'))

            flash("Username atau Password salah!", "danger")
        except Exception as e:
            flash(f"Koneksi Database Gagal: {e}", "danger")
        finally:
            if 'db' in locals() and db.is_connected():
                cursor.close()
                db.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah berhasil keluar dari sistem.", "success")
    return redirect(url_for('login'))

# --- TAMBAHAN: Handler untuk Error 404 ---
@app.errorhandler(404)
def page_not_found(e):
    return "<h1>Halaman Tidak Ditemukan (404)</h1><a href='/'>Kembali ke Login</a>", 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)