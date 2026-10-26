from flask import Blueprint, render_template, session, redirect, url_for, request, flash
import mysql.connector
from datetime import datetime

# Inisialisasi Blueprint
admin_bp = Blueprint('admin', __name__)

# Fungsi koneksi database
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_caleg_jaktim_tibi" #
    )

@admin_bp.route('/dashboard')
def dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # 1. Ambil Total Target (SUM dari tabel target_wilayah)
    cursor.execute("SELECT SUM(jumlah_target) as total FROM target_wilayah")
    res_target = cursor.fetchone()
    # Simpan ke variabel 'target' sesuai HTML
    target = res_target['total'] or 0

    # 2. Ambil Total Dukungan (COUNT dari tabel pendukung)
    cursor.execute("SELECT COUNT(*) as total FROM pendukung")
    res_masuk = cursor.fetchone()
    # Simpan ke variabel 'masuk' sesuai HTML
    masuk = res_masuk['total'] or 0

    # 3. Hitung Persentase
    persen = 0
    if target > 0:
        persen = round((masuk / target) * 100, 1)

    # 4. Ambil Riwayat Instruksi (untuk bagian bawah dashboard)
    cursor.execute("SELECT * FROM instruksi ORDER BY tanggal_kirim DESC LIMIT 5")
    logs = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('admin/dashboard_admin.html', 
                           target=target, 
                           masuk=masuk, 
                           persen=persen,
                           logs=logs)

@admin_bp.route('/data-target')
def data_target():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Query untuk mengambil data target per kecamatan dan jumlah pendukung saat ini
    query = """
        SELECT 
            k.id_kecamatan, 
            k.nama_kecamatan, 
            COALESCE(tw.jumlah_target, 0) as target,
            (SELECT COUNT(*) FROM pendukung p WHERE p.id_kecamatan = k.id_kecamatan) as realisasi
        FROM kecamatan k
        LEFT JOIN target_wilayah tw ON k.id_kecamatan = tw.id_kecamatan
        ORDER BY k.nama_kecamatan ASC
    """
    cursor.execute(query)
    list_target = cursor.fetchall()

    # Hitung total untuk footer
    total_target = sum(item['target'] for item in list_target)
    total_realisasi = sum(item['realisasi'] for item in list_target)

    cursor.close()
    db.close()

    return render_template('admin/data_target_suara_admin.html', 
                           list_target=list_target, 
                           total_target=total_target, 
                           total_realisasi=total_realisasi)

@admin_bp.route('/hapus-target/<int:id_kecamatan>', methods=['GET', 'POST'])
def hapus_target(id_kecamatan):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            # Menghapus entri target, realisasi pendukung tetap aman di tabel pendukung
            cursor.execute("DELETE FROM target_wilayah WHERE id_kecamatan = %s", (id_kecamatan,))
            db.commit()
            flash("Target wilayah berhasil dihapus!", "success")
        except Exception as e:
            db.rollback()
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()
            db.close()
        return redirect(url_for('admin.data_target'))

    # GET: Tampilkan halaman konfirmasi hapus
    cursor.execute("""
        SELECT k.id_kecamatan, k.nama_kecamatan, COALESCE(tw.jumlah_target, 0) as target 
        FROM kecamatan k
        LEFT JOIN target_wilayah tw ON k.id_kecamatan = tw.id_kecamatan
        WHERE k.id_kecamatan = %s
    """, (id_kecamatan,))
    data = cursor.fetchone()
    
    cursor.close()
    db.close()

    return render_template('admin/hapus_data_target_admin.html', data=data)

@admin_bp.route('/edit-target/<int:id_kecamatan>', methods=['GET', 'POST'])
def edit_target(id_kecamatan):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        target_baru = request.form.get('target_suara')
        
        # 1. Cek apakah id_kecamatan ini sudah ada di tabel target_wilayah
        cursor.execute("SELECT id_kecamatan FROM target_wilayah WHERE id_kecamatan = %s", (id_kecamatan,))
        ada_data = cursor.fetchone()

        try:
            if ada_data:
                # 2. Jika sudah ada, kita UPDATE angkanya saja
                query = "UPDATE target_wilayah SET jumlah_target = %s WHERE id_kecamatan = %s"
                cursor.execute(query, (target_baru, id_kecamatan))
            else:
                # 3. Jika belum ada (kasus data baru), kita INSERT
                query = "INSERT INTO target_wilayah (id_kecamatan, jumlah_target) VALUES (%s, %s)"
                cursor.execute(query, (id_kecamatan, target_baru))
            
            db.commit()
            flash("Target berhasil diperbarui!", "success")
        except Exception as e:
            db.rollback()
            flash(f"Gagal menyimpan: {e}", "danger")
        finally:
            cursor.close()
            db.close()
            
        return redirect(url_for('admin.data_target'))

    # Bagian GET: Menampilkan data ke Form Edit
    query_data = """
        SELECT k.id_kecamatan, k.nama_kecamatan, COALESCE(tw.jumlah_target, 0) as target 
        FROM kecamatan k
        LEFT JOIN target_wilayah tw ON k.id_kecamatan = tw.id_kecamatan
        WHERE k.id_kecamatan = %s
    """
    cursor.execute(query_data, (id_kecamatan,))
    data = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template('admin/edit_data_target.html', data=data)

@admin_bp.route('/kirim-instruksi', methods=['POST'])
def kirim_instruksi():
    # Proteksi tambahan agar tidak bisa ditembak POST dari luar
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    kategori = request.form.get('kategori')
    pesan = request.form.get('pesan')
    id_admin = session.get('user_id') # Mengambil ID admin yang sedang login
    
    db = get_db()
    cursor = db.cursor()
    # Query disesuaikan dengan skema: id_admin, kategori, isi_pesan
    query = "INSERT INTO instruksi (id_admin, kategori, isi_pesan) VALUES (%s, %s, %s)"
    cursor.execute(query, (id_admin, kategori, pesan))
    db.commit()
    cursor.close()
    db.close()
    
    flash("Instruksi Berhasil Dikirim!", "success") 
    return redirect(url_for('admin.dashboard'))

# Menampilkan Riwayat Instruksi
@admin_bp.route('/riwayat-instruksi')
def riwayat_instruksi_admin():
    # Proteksi halaman: pastikan user sudah login dan perannya adalah admin/petugas
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        query = "SELECT id_instruksi, tanggal_kirim, kategori, isi_pesan FROM instruksi ORDER BY tanggal_kirim DESC"
        cursor.execute(query)
        riwayat = cursor.fetchall()
    except Exception as e:
        print(f"Error: {e}")
        riwayat = []
    finally:
        cursor.close()
        db.close()

    return render_template('admin/instruksi_admin.html', 
                           riwayat_instruksi=riwayat)

# Menghapus Instruksi
@admin_bp.route('/hapus-instruksi/<int:id>', methods=['GET', 'POST'])
def hapus_instruksi(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Ambil info 'asal' dari URL (default ke dashboard jika tidak ada)
    halaman_asal = request.args.get('asal', 'dashboard')

    if request.method == 'GET':
        cursor.execute("SELECT * FROM instruksi WHERE id_instruksi = %s", (id,))
        data = cursor.fetchone()
        if not data:
            return redirect(url_for('admin.dashboard'))
            
        # Kirim variabel 'halaman_asal' ke template konfirmasi
        return render_template('admin/hapus_instruksi_admin.html', ins=data, asal=halaman_asal)

    if request.method == 'POST':
        try:
            cursor.execute("DELETE FROM instruksi WHERE id_instruksi = %s", (id,))
            db.commit()
            flash("Instruksi berhasil dihapus!", "success")
        except Exception as e:
            db.rollback()
            flash("Gagal menghapus data.", "danger")
        finally:
            cursor.close()
            db.close()
            
        if halaman_asal == 'riwayat':
            return redirect(url_for('admin.riwayat_instruksi_admin'))
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/data-konstituen')
def data_konstituen_admin():
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

    # Logika Pencarian Nama atau NIK
    if search_query:
        query += " AND (p.nama LIKE %s OR p.nik LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    # Logika Filter per Kecamatan
    if filter_kecamatan:
        query += " AND p.id_kecamatan = %s"
        params.append(filter_kecamatan)

    query += " ORDER BY tanggal_tampil DESC, p.id_pendukung DESC"
    
    cursor.execute(query, params)
    konstituen = cursor.fetchall()

    # Ambil list kecamatan untuk dropdown filter
    cursor.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatan_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('admin/data_konstituen_admin.html', 
                           konstituen=konstituen, 
                           kecamatan=kecamatan_list,
                           search_query=search_query,
                           filter_kecamatan=filter_kecamatan)

@admin_bp.route('/tambah-konstituen', methods=['GET', 'POST'])
def tambah_data_konstituen_admin():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    if request.method == 'POST':
        nama = request.form.get('nama')
        nik = request.form.get('nik')
        no_hp = request.form.get('no_hp')
        id_kec = request.form.get('id_kecamatan')
        alamat = request.form.get('alamat')
        
        waktu_sekarang = datetime.now()

        cursor = db.cursor()
        try:
            cursor.execute("SELECT id_pendukung FROM pendukung WHERE nik = %s", (nik,))
            if cursor.fetchone():
                flash(f"NIK {nik} sudah terdaftar!", "danger")
            else:
                # 1. Input ke tabel pendukung (Data Utama) dengan tanggal_daftar
                query_p = """
                    INSERT INTO pendukung (nama, nik, no_hp, id_kecamatan, alamat, tanggal_daftar) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query_p, (nama, nik, no_hp, id_kec, alamat, waktu_sekarang.date()))
                
                id_baru = cursor.lastrowid 

                # 2. Input ke tabel dukungan agar tgl_input terisi
                query_d = "INSERT INTO dukungan (id_pendukung, id_relawan, tanggal_input) VALUES (%s, %s, %s)"
                cursor.execute(query_d, (id_baru, None, waktu_sekarang))

                db.commit()
                flash("Data berhasil ditambahkan oleh Admin!", "success")
                return redirect(url_for('admin.data_konstituen_admin'))
        except Exception as e:
            db.rollback()
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()

    cursor_get = db.cursor(dictionary=True)
    cursor_get.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatans_list = cursor_get.fetchall()
    cursor_get.close()
    db.close()

    return render_template('admin/tambah_data_konstituen_admin.html', kecamatan=kecamatans_list)

@admin_bp.route('/edit-konstituen/<int:id>', methods=['GET', 'POST'])
def edit_konstituen_admin(id):
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
            return redirect(url_for('admin.data_konstituen_admin'))
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
    
    return render_template('admin/edit_data_konstituen_admin.html', p=person, kecamatans=kecamatans)

@admin_bp.route('/konfirmasi-hapus-konstituen/<int:id>')
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
        return redirect(url_for('admin.data_konstituen_admin'))

    return render_template('admin/hapus_data_konstituen_admin.html', person=person)

@admin_bp.route('/hapus-konstituen-eksekusi/<int:id>', methods=['POST'])
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

    return redirect(url_for('admin.data_konstituen_admin'))

# --- MANAJEMEN RELAWAN ---
@admin_bp.route('/manajemen-relawan')
def manajemen_relawan_admin():
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # Mengambil data relawan beserta nama kecamatannya
        query = """
            SELECT r.*, k.nama_kecamatan 
            FROM relawan r
            LEFT JOIN kecamatan k ON r.id_kecamatan = k.id_kecamatan
            ORDER BY r.nama_relawan ASC
        """
        cursor.execute(query)
        data_relawan = cursor.fetchall()
    except Exception as e:
        print(f"Error Database: {e}")
        data_relawan = []
    finally:
        cursor.close()
        db.close()

    return render_template('admin/rekrutmen_relawan_admin.html', relawan=data_relawan)

@admin_bp.route('/tambah-relawan', methods=['GET', 'POST'])
def tambah_relawan_admin():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        # 1. Ambil data dari form (TAMBAHKAN EMAIL DI SINI)
        nama = request.form.get('nama')
        no_hp = request.form.get('no_hp')
        email = request.form.get('email') # <--- Tambahkan ini
        username = request.form.get('username')
        id_kec = request.form.get('id_kecamatan')
        password_default = "relawan123"

        try:
            # 2. Ambil nama kecamatan
            cursor.execute("SELECT nama_kecamatan FROM kecamatan WHERE id_kecamatan = %s", (id_kec,))
            kec_data = cursor.fetchone()
            nama_wilayah = kec_data['nama_kecamatan'] if kec_data else "-"

            # 3. CEK ID TERAKHIR
            cursor.execute("SELECT MAX(id_relawan) as max_id FROM relawan")
            res_id = cursor.fetchone()
            max_id_val = res_id['max_id'] if res_id and res_id['max_id'] else 0
            next_id = max_id_val + 1

            # 4. QUERY INSERT (TAMBAHKAN KOLOM EMAIL)
            query = """
                INSERT INTO relawan (id_relawan, username, password, nama_relawan, no_hp, email, wilayah_tugas, id_kecamatan) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (next_id, username, password_default, nama, no_hp, email, nama_wilayah, id_kec))
            
            db.commit()
            
            if cursor.rowcount > 0:
                flash("Relawan Berhasil Didaftarkan!", "success")
                return redirect(url_for('admin.manajemen_relawan_admin'))

        except Exception as e:
            db.rollback()
            flash(f"Error Database: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()

    cursor.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatans = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('admin/tambah_relawan_admin.html', kecamatans=kecamatans)

@admin_bp.route('/edit-relawan/<int:id>', methods=['GET', 'POST'])
def edit_relawan_admin(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        # Ambil data sesuai kolom di database
        nama = request.form.get('nama')
        no_hp = request.form.get('no_hp')
        id_kecamatan = request.form.get('id_kecamatan')
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        try:
            # Ambil nama kecamatan untuk kolom wilayah_tugas
            cursor.execute("SELECT nama_kecamatan FROM kecamatan WHERE id_kecamatan = %s", (id_kecamatan,))
            kec_data = cursor.fetchone()
            nama_wilayah = kec_data['nama_kecamatan'] if kec_data else "-"

            if new_password:
                # Update dengan password baru
                query = """
                    UPDATE relawan 
                    SET nama_relawan=%s, no_hp=%s, id_kecamatan=%s, wilayah_tugas=%s, email=%s, password=%s
                    WHERE id_relawan=%s
                """
                cursor.execute(query, (nama, no_hp, id_kecamatan, nama_wilayah, email, new_password, id))
            else:
                # Update tanpa mengubah password
                query = """
                    UPDATE relawan 
                    SET nama_relawan=%s, no_hp=%s, id_kecamatan=%s, wilayah_tugas=%s, email=%s
                    WHERE id_relawan=%s
                """
                cursor.execute(query, (nama, no_hp, id_kecamatan, nama_wilayah, email, id))
            
            db.commit()
            flash("Data relawan berhasil diperbarui!", "success")
            return redirect(url_for('admin.manajemen_relawan_admin'))
            
        except Exception as e:
            db.rollback()
            print(f"DEBUG ERROR: {str(e)}")
            flash("Gagal memperbarui data.", "danger")
        finally:
            cursor.close()
            db.close()

    cursor.execute("SELECT * FROM relawan WHERE id_relawan = %s", (id,))
    relawan = cursor.fetchone()
    cursor.execute("SELECT * FROM kecamatan ORDER BY nama_kecamatan ASC")
    kecamatans = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('admin/edit_relawan_admin.html', relawan=relawan, kecamatans=kecamatans)

@admin_bp.route('/konfirmasi-hapus-relawan/<int:id>', methods=['GET'])
def konfirmasi_hapus_relawan(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM relawan WHERE id_relawan = %s", (id,))
    relawan = cursor.fetchone() # Pakai fetchone agar tidak jadi 'list object'
    cursor.close()
    db.close()
    
    if not relawan:
        return "Data tidak ditemukan", 404
        
    return render_template('admin/hapus_data_relawan_admin.html', relawan=relawan)

@admin_bp.route('/hapus-relawan-eksekusi/<int:id>', methods=['POST'])
def hapus_relawan_eksekusi(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM relawan WHERE id_relawan = %s", (id,))
        db.commit()
        flash("Akun relawan berhasil dihapus!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Gagal menghapus: {e}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('admin.manajemen_relawan_admin'))

@admin_bp.route('/laporan-statistik')
def laporan_statistik_admin():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1. Total Konstituen
        cursor.execute("SELECT COUNT(*) as total FROM pendukung")
        total_k = cursor.fetchone()['total'] or 0

        # 2. Total Relawan (Hapus WHERE status karena di DB tidak ada kolom status)
        cursor.execute("SELECT COUNT(*) as total FROM relawan")
        total_r = cursor.fetchone()['total'] or 0

        # 3. Statistik per Kecamatan
        query_stats = """
            SELECT k.nama_kecamatan, COUNT(p.id_pendukung) as jumlah
            FROM kecamatan k
            LEFT JOIN pendukung p ON k.id_kecamatan = p.id_kecamatan
            GROUP BY k.id_kecamatan, k.nama_kecamatan
            ORDER BY jumlah DESC
        """
        cursor.execute(query_stats)
        stats = cursor.fetchall()

    except Exception as e:
        print(f"Error Database: {e}")
        total_k, total_r, stats = 0, 0, []
    finally:
        cursor.close()
        db.close()

    return render_template(
        'admin/laporan_dan_statistik_admin.html', 
        total_k=total_k, 
        total_r=total_r, 
        stats=stats
    )