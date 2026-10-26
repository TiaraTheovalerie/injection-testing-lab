import pymysql
from werkzeug.security import generate_password_hash

class Config:
    def __init__(self):
        self.db_host = 'localhost'
        self.db_user = 'root'
        self.db_password = ''
        self.db_name = 'db_caleg_jaktim_tibi' # Pastikan nama database sesuai

    def _get_connection(self):
        return pymysql.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )

    def check_db_connection(self):
        try:
            conn = self._get_connection()
            conn.ping(reconnect=True)
            conn.close()
            return True
        except pymysql.MySQLError:
            return False

    # --- Manajemen Pengguna (Admin & Petugas) ---
    # Di dalam config.py
    def get_user_by_username(self, username):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Perhatikan: password (dari DB) as password_hash (untuk Python)
                sql = "SELECT id_admin, username, password as password_hash, nama_admin as nama_lengkap FROM admin WHERE username = %s"
                cursor.execute(sql, (username,))
                return cursor.fetchone()
        finally:
            conn.close()

    def add_user(self, user_data):
        """Menambah Admin atau Petugas baru"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                hashed_password = generate_password_hash(user_data['password'])
                sql = """INSERT INTO Pengguna (username, password_hash, nama_lengkap, peran) 
                         VALUES (%s, %s, %s, %s)"""
                cursor.execute(sql, (
                    user_data['username'],
                    hashed_password,
                    user_data['nama_lengkap'],
                    user_data['peran'] # 'admin' atau 'petugas'
                ))
                conn.commit()
                return cursor.lastrowid
        except pymysql.MySQLError as e:
            print(f"Error adding user: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    # --- Manajemen Konstituen (Data Pendukung) ---
    def add_konstituen(self, data):
        """Petugas menginput data pendukung baru"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """INSERT INTO Konstituen (nama, nik, alamat, kecamatan, kelurahan, id_petugas) 
                         VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, (
                    data['nama'], data['nik'], data['alamat'], 
                    data['kecamatan'], data['kelurahan'], data['id_petugas']
                ))
                conn.commit()
                return True
        except pymysql.MySQLError as e:
            print(f"Error input konstituen: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_statistik_per_wilayah(self):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Join pendukung ke kecamatan berdasarkan id_kecamatan
                sql = """
                    SELECT k.nama_kecamatan as kecamatan, COUNT(p.id_pendukung) as total 
                    FROM kecamatan k 
                    LEFT JOIN pendukung p ON k.id_kecamatan = p.id_kecamatan 
                    GROUP BY k.nama_kecamatan
                """
                cursor.execute(sql)
                return cursor.fetchall()
        finally:
            conn.close()

    def get_konstituen_by_petugas(self, id_petugas):
        """Melihat daftar warga yang didata oleh petugas tertentu"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM Konstituen WHERE id_petugas = %s ORDER BY created_at DESC"
                cursor.execute(sql, (id_petugas,))
                return cursor.fetchall()
        finally:
            conn.close()
    
    def get_users_by_role(self, peran=None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id_relawan, nama_relawan, no_hp, wilayah_tugas FROM relawan"
                cursor.execute(sql)
                return cursor.fetchall()
        finally:
            conn.close()