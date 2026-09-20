"""
Variabel turunan (section 3 AMBA Kamus Variabel).

Satu file per kelompok indikator. Setiap fungsi compute_* menerima data
mentah (list of dict / pandas.DataFrame) yang SUDAH difetch dan disimpan
oleh endpoints/ + storage/, dan mengembalikan dict indikator turunan untuk
satu (symbol, as_of_date).

Tidak ada modul di sini yang memanggil Sectors API secara langsung --
semua input berasal dari tabel Supabase yang sudah terisi.
"""
