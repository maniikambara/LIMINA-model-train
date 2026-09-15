"""
test_metrics.py -- Uji metrik dengan kasus yang jawabannya diketahui
=======================================================================

Metrik yang salah hitung akan menghasilkan angka yang terlihat wajar
tetapi keliru, dan kesalahan seperti itu tidak akan pernah ketahuan tanpa
pengujian (docs/rancangan/AMBANG-peran-model-dan-evaluasi.md bagian 9).
"""

import numpy as np
import pandas as pd

from limina import metrics


def test_precision_at_k_kasus_sederhana():
    # 5 emiten, skor menurun sempurna, 2 emiten teratas positif
    y_true = [1, 1, 0, 0, 0]
    skor = [5, 4, 3, 2, 1]
    assert metrics.precision_at_k(y_true, skor, k=2) == 1.0
    assert metrics.precision_at_k(y_true, skor, k=5) == 0.4


def test_precision_at_k_urutan_terbalik():
    # Skor tidak selaras label sama sekali: dua teratas skor justru negatif
    y_true = [0, 0, 1, 1]
    skor = [10, 9, 1, 0]
    assert metrics.precision_at_k(y_true, skor, k=2) == 0.0


def test_recall_90h_kasus_sederhana():
    y_true = [1, 1, 0, 0, 1]
    skor = [5, 4, 3, 2, 1]  # dua peristiwa masuk top-3, satu tidak
    assert abs(metrics.recall_90h(y_true, skor, k=3) - (2 / 3)) < 1e-9


def test_recall_90h_tanpa_positif_menghasilkan_nan():
    y_true = [0, 0, 0]
    skor = [1, 2, 3]
    assert np.isnan(metrics.recall_90h(y_true, skor, k=2))


def test_auc_pemisahan_sempurna():
    y_true = [0, 0, 1, 1]
    skor = [1, 2, 3, 4]
    assert metrics.hitung_auc(y_true, skor) == 1.0


def test_auc_hanya_satu_kelas_menghasilkan_nan():
    y_true = [1, 1, 1]
    skor = [1, 2, 3]
    assert np.isnan(metrics.hitung_auc(y_true, skor))


def test_kalibrasi_ambang_top_20_dari_100():
    # Skor 1..100, ambang untuk top 20 dari 100 emiten seharusnya sekitar 80
    skor_latih = np.arange(1, 101)
    ambang = metrics.kalibrasi_ambang(skor_latih, jumlah_top=20, total_cakupan=100)
    assert 78 <= ambang <= 82


def test_kalibrasi_ambang_jumlah_top_melebihi_cakupan_tidak_meledak():
    # Cakupan hanya 5 titik (mis. riwayat mingguan pendek untuk emiten
    # yang baru masuk cakupan), jumlah_top diminta 20. Tanpa batas ini,
    # np.percentile menerima argumen persentil negatif dan melempar
    # ValueError -- lihat catatan di limina/metrics.py::kalibrasi_ambang.
    skor_latih = np.array([0.1, 0.5, 0.9, 0.3, 0.7])
    ambang = metrics.kalibrasi_ambang(skor_latih, jumlah_top=20, total_cakupan=len(skor_latih))
    assert ambang == float(np.min(skor_latih))


def test_hitung_selisih_waktu_terdeteksi_dan_bertahan():
    tanggal = pd.date_range("2024-01-01", periods=6, freq="30D")
    # Skor melewati ambang (0.5) pada indeks 3 dan bertahan di indeks 4
    riwayat = pd.DataFrame({"tanggal": tanggal, "skor": [0.1, 0.2, 0.3, 0.6, 0.7, 0.9]})
    tanggal_peristiwa = tanggal[-1] + pd.Timedelta(days=10)

    hasil = metrics.hitung_selisih_waktu(riwayat, ambang=0.5, tanggal_peristiwa=tanggal_peristiwa)

    assert hasil["terdeteksi"] is True
    assert hasil["tanggal_terdeteksi"] == tanggal[3]
    selisih_seharusnya = (tanggal_peristiwa - tanggal[3]).days
    assert hasil["selisih_hari"] == selisih_seharusnya


def test_hitung_selisih_waktu_lonjakan_sesaat_tidak_dihitung():
    tanggal = pd.date_range("2024-01-01", periods=5, freq="30D")
    # Skor melewati ambang sesaat di indeks 1 lalu turun lagi, baru
    # benar-benar bertahan mulai indeks 3-4
    riwayat = pd.DataFrame({"tanggal": tanggal, "skor": [0.1, 0.9, 0.1, 0.6, 0.7]})
    tanggal_peristiwa = tanggal[-1] + pd.Timedelta(days=5)

    hasil = metrics.hitung_selisih_waktu(riwayat, ambang=0.5, tanggal_peristiwa=tanggal_peristiwa)

    assert hasil["terdeteksi"] is True
    assert hasil["tanggal_terdeteksi"] == tanggal[3]  # bukan tanggal[1]


def test_hitung_selisih_waktu_tidak_pernah_melewati_ambang():
    tanggal = pd.date_range("2024-01-01", periods=4, freq="30D")
    riwayat = pd.DataFrame({"tanggal": tanggal, "skor": [0.1, 0.2, 0.15, 0.2]})
    tanggal_peristiwa = tanggal[-1] + pd.Timedelta(days=5)

    hasil = metrics.hitung_selisih_waktu(riwayat, ambang=0.5, tanggal_peristiwa=tanggal_peristiwa)

    assert hasil["terdeteksi"] is False
    assert hasil["selisih_hari"] is None


def test_ringkas_selisih_waktu_mengecualikan_kejadian_terlewat_dari_median():
    daftar = [
        {"terdeteksi": True, "selisih_hari": 10, "tanggal_terdeteksi": None},
        {"terdeteksi": True, "selisih_hari": 20, "tanggal_terdeteksi": None},
        {"terdeteksi": False, "selisih_hari": None, "tanggal_terdeteksi": None},
    ]
    ringkasan = metrics.ringkas_selisih_waktu(daftar)
    assert ringkasan["median_hari"] == 15.0
    assert ringkasan["kejadian_terlewat"] == 1
    assert ringkasan["jumlah_terdeteksi"] == 2


def test_akurasi_internal_tidak_dipakai_sebagai_precision():
    # Sanity check nama fungsi: akurasi tinggi walau model tidak berguna
    # pada kelas timpang, justru menunjukkan kenapa metrik ini dilarang
    # dipakai publik.
    y_true = [0] * 95 + [1] * 5
    y_pred = [0] * 100  # menebak semua aman
    akurasi = metrics.akurasi_internal_saja(y_true, y_pred)
    assert akurasi == 0.95  # tinggi, tapi model ini tidak menangkap satupun positif
