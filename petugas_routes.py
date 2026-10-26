from flask import Blueprint, render_template, session, redirect, url_for, request, flash
import mysql.connector
from datetime import datetime

# Inisialisasi Blueprint
petugas_bp = Blueprint('petugas', __name__)

# Fungsi koneksi database
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_caleg_jaktim_tibi" #
    )

@petugas_bp.route('/dashboard')
def dashboard_petugas():
    id_kecamatan = session.get('id_kecamatan')
    id_relawan = session.get('id_user') 
    
    db = get_db()
    cursor = db.cursor(dictionary=True)

    target_suara = 0
    if id_kecamatan:
        # Tambahkan print untuk cek di terminal apakah ID muncul
        print(f"DEBUG: Mencari target untuk kecamatan ID: {id_kecamatan}")
        
        cursor.execute("""
            SELECT jumlah_target FROM target_wilayah 
            WHERE id_kecamatan = %s
        """, (id_kecamatan,))
        target_data = cursor.fetchone()
        if target_data:
            target_suara = target_data['jumlah_target']
    else:
        print("DEBUG: id_kecamatan TIDAK DITEMUKAN di session!")

    # 2. Hitung Dukungan Masuk
    total_dukungan = 0
    if id_relawan:
        cursor.execute("""
            SELECT COUNT(*) as total FROM dukungan 
            WHERE id_relawan = %s
        """, (id_relawan,))
        result = cursor.fetchone()
        total_dukungan = result['total'] if result else 0

    # 3. Hitung Persentase
    persen = 0
    if target_suara > 0:
        persen = round((total_dukungan / target_suara * 100), 1)

    # 4. Ambil Instruksi
    try:
        cursor.execute("SELECT * FROM instruksi ORDER BY tanggal_kirim DESC LIMIT 1")
        instruksi_terbaru = cursor.fetchone()

        cursor.execute("SELECT * FROM instruksi ORDER BY tanggal_kirim DESC LIMIT 10 OFFSET 1")
        arsip_instruksi = cursor.fetchall()
    except:
        instruksi_terbaru = None
        arsip_instruksi = []

    # 5. Hitung H-Voting
    voting_day = datetime(2029, 2, 14)
    delta = voting_day - datetime.now()
    h_voting = max(0, delta.days)

    cursor.close()
    
    return render_template('petugas/dashboard_petugas.html', 
                           target=target_suara, 
                           realisasi=total_dukungan,
                           persen=persen,
                           h_voting=h_voting,
                           terbaru=instruksi_terbaru,
                           arsip=arsip_instruksi)

@petugas_bp.route('/data-konstituen')
def data_konstituen_petugas():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    search_query = request.args.get('q', '').strip()
    filter_kecamatan = request.args.get('kecamatan', '').strip()

    query = """
        SELECT p.*, k.nama_kecamatan, 
               IFNULL(r.nama_relawan, 'Admin') as nama_relawan, 
               COALESCE(d.tanggal_input, p.tanggal_daftar) as tanggal_tampil
        FROM pendukung p
        LEFT JOIN kecamatan k ON p.id_kecamatan = k.id_kecamatan
        LEFT JOIN dukungan d ON p.id_pendukung = d.id_pendukung
        LEFT JOIN relawan r ON d.id_relawan = r.id_relawan
        WHERE 1=1
    """
    params = []
    if search_query:
        query += " AND (p.nama LIKE %s OR p.nik LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    if filter_kecamatan:
        query += " AND p.id_kecamatan = %s"
        params.append(filter_kecamatan)

    query += " ORDER BY tanggal_tampil DESC, p.id_pendukung DESC"
    
    cursor.execute(query, params)
    konstituen = cursor.fetchall()

    cursor.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatan_list = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('petugas/data_konstituen_petugas.html', 
                           konstituen=konstituen, 
                           kecamatan=kecamatan_list,
                           search_query=search_query,
                           filter_kecamatan=filter_kecamatan)

@petugas_bp.route('/tambah-konstituen', methods=['GET', 'POST'])
def tambah_data_konstituen_petugas():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    id_kecamatan_petugas = session.get('id_kecamatan')
    db = get_db()

    if request.method == 'POST':
        nama = request.form.get('nama')
        nik = request.form.get('nik')
        no_hp = request.form.get('no_hp')
        id_kec = request.form.get('id_kecamatan')
        alamat = request.form.get('alamat')
        id_relawan = session.get('id_user')
        
        # Ambil waktu sekarang untuk kedua tabel
        waktu_sekarang = datetime.now()

        cursor = db.cursor()
        try:
            cursor.execute("SELECT id_pendukung FROM pendukung WHERE nik = %s", (nik,))
            if cursor.fetchone():
                flash(f"Gagal! NIK {nik} sudah terdaftar.", "danger")
            else:
                query_p = """
                    INSERT INTO pendukung (nama, nik, no_hp, id_kecamatan, alamat, tanggal_daftar) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query_p, (nama, nik, no_hp, id_kec, alamat, waktu_sekarang.date()))
                id_pendukung_baru = cursor.lastrowid

                # Input ke tabel dukungan (Tetap seperti biasa untuk timestamp)
                query_d = "INSERT INTO dukungan (id_pendukung, id_relawan, tanggal_input) VALUES (%s, %s, %s)"
                cursor.execute(query_d, (id_pendukung_baru, id_relawan, waktu_sekarang))

                db.commit()
                flash("Data Konstituen berhasil ditambahkan!", "success")
                return redirect(url_for('petugas.data_konstituen_petugas'))
        except Exception as e:
            db.rollback()
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()

    cursor_get = db.cursor(dictionary=True)
    cursor_get.execute("SELECT id_kecamatan, nama_kecamatan FROM kecamatan WHERE id_kecamatan = %s", (id_kecamatan_petugas,))
    data_kecamatan = cursor_get.fetchall()
    cursor_get.close()
    db.close()
    return render_template('petugas/input_data_petugas.html', kecamatans=data_kecamatan)

@petugas_bp.route('/edit-konstituen/<int:id>', methods=['GET', 'POST'])
def edit_konstituen_petugas(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form.get('nama')
        nik = request.form.get('nik')
        no_hp = request.form.get('no_hp')
        id_kec = request.form.get('id_kecamatan')
        alamat = request.form.get('alamat')

        try:
            query = """
                UPDATE pendukung 
                SET nama=%s, nik=%s, no_hp=%s, id_kecamatan=%s, alamat=%s 
                WHERE id_pendukung=%s
            """
            cursor.execute(query, (nama, nik, no_hp, id_kec, alamat, id))
            db.commit()
            flash("Data berhasil diperbarui!", "success")
            cursor.close()
            db.close()
            return redirect(url_for('petugas.data_konstituen_petugas'))
        except Exception as e:
            db.rollback()
            flash(f"Gagal update: {e}", "danger")

    # Load data lama untuk form edit
    cursor.execute("SELECT * FROM pendukung WHERE id_pendukung = %s", (id,))
    person = cursor.fetchone()
    
    cursor.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatans = cursor_get = cursor.fetchall()

    cursor.close()
    db.close()
    
    return render_template('petugas/edit_data_petugas.html', p=person, kecamatans=kecamatans)

@petugas_bp.route('/konfirmasi-hapus-konstituen/<int:id>')
def konfirmasi_hapus_konstituen(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # GUNAKAN JOIN agar nama_kecamatan bisa terbaca oleh HTML
    query = """
        SELECT p.*, k.nama_kecamatan 
        FROM pendukung p
        LEFT JOIN kecamatan k ON p.id_kecamatan = k.id_kecamatan
        WHERE p.id_pendukung = %s
    """
    
    cursor.execute(query, (id,))
    person = cursor.fetchone()
    cursor.close()
    db.close()

    if not person:
        flash("Data tidak ditemukan!", "danger")
        return redirect(url_for('petugas.data_konstituen_petugas'))

    return render_template('petugas/hapus_data_petugas.html', person=person)

@petugas_bp.route('/hapus-konstituen-eksekusi/<int:id>', methods=['POST'])
def hapus_konstituen_eksekusi(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM pendukung WHERE id_pendukung = %s", (id,))
        db.commit()
        flash("Data berhasil dihapus!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('petugas.data_konstituen_petugas'))

@petugas_bp.route('/daftar-dukungan-wilayah')
def daftar_dukungan_wilayah():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    id_kecamatan_petugas = session.get('id_kecamatan')
    id_relawan_petugas = session.get('id_user') # ID relawan yang login
    
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 1. Ambil Nama Kecamatan & Target
    cursor.execute("""
        SELECT k.nama_kecamatan, t.jumlah_target 
        FROM kecamatan k
        LEFT JOIN target_wilayah t ON k.id_kecamatan = t.id_kecamatan
        WHERE k.id_kecamatan = %s
    """, (id_kecamatan_petugas,))
    info_wilayah = cursor.fetchone()

    # 2. Hitung Realisasi Dukungan
    cursor.execute("""
        SELECT COUNT(*) as total 
        FROM dukungan 
        WHERE id_relawan = %s
    """, (id_relawan_petugas,))
    realisasi = cursor.fetchone()['total']

    # 3. Ambil List Pendukung yang didaftarkan oleh relawan ini
    cursor.execute("""
        SELECT p.nama, p.nik, p.alamat, d.tanggal_input
        FROM pendukung p
        JOIN dukungan d ON p.id_pendukung = d.id_pendukung
        WHERE d.id_relawan = %s
        ORDER BY d.tanggal_input DESC
    """, (id_relawan_petugas,))
    daftar_pendukung = cursor.fetchall()

    cursor.close()
    db.close()

    # Hitung Persentase
    target = info_wilayah['jumlah_target'] if info_wilayah and info_wilayah['jumlah_target'] else 0
    persen = round((realisasi / target * 100), 1) if target > 0 else 0
    
    return render_template('petugas/daftar_dukungan.html', 
                           kecamatan_nama=info_wilayah['nama_kecamatan'] if info_wilayah else "Tidak Diketahui",
                           total_target=target,
                           total_realisasi=realisasi,
                           persentase_total=persen,
                           pendukung=daftar_pendukung)