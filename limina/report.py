"""
report.py -- Ringkasan hasil ke berkas markdown
==================================================

Menulis ringkasan yang bisa langsung dibaca tanpa perlu membuka notebook,
ke artifacts/ringkasan_evaluasi.md. Dipanggil di akhir notebook 04
setiap siklus latih, sehingga isinya selalu mencerminkan hasil latihan
paling baru, bukan satu snapshot yang ditulis sekali lalu dilupakan.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def tulis_ringkasan_markdown(
    path: str | Path,
    *,
    hasil_lintas_potret: pd.DataFrame,
    ringkasan_selisih: dict,
    keputusan_gerbang: dict,
    hasil_kebocoran: dict,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ringkas_precision = (
        hasil_lintas_potret.pivot(
            index="tanggal_potret", columns="kandidat", values="precision_at_20"
        )
        .round(3)
        .to_markdown()
    )

    baris = [
        "# Ringkasan Evaluasi LIMINA",
        "",
        f"Dibuat otomatis oleh `limina/report.py` pada notebook 04, setiap "
        f"kali siklus latih dijalankan ulang. Mencerminkan hasil latihan "
        f"paling baru, bukan snapshot satu kali.",
        "",
        "## Pemeriksaan Kebocoran",
        "",
        f"- Status: {'LOLOS' if hasil_kebocoran.get('lolos') else 'GAGAL'}",
        f"- AUC pengacakan label: {hasil_kebocoran.get('auc_pengacakan_label'):.3f}"
        if hasil_kebocoran.get("auc_pengacakan_label") is not None
        else "- AUC pengacakan label: tidak dihitung",
    ]
    if hasil_kebocoran.get("masalah"):
        baris.append("- Masalah ditemukan:")
        for m in hasil_kebocoran["masalah"]:
            baris.append(f"  - {m}")

    baris += [
        "",
        "## Precision@20 Lintas Potret",
        "",
        ringkas_precision,
        "",
        "## Selisih Waktu terhadap Label Resmi",
        "",
        f"- Median: {ringkasan_selisih.get('median_hari')} hari",
        f"- P25-P75: {ringkasan_selisih.get('p25_hari')} - {ringkasan_selisih.get('p75_hari')} hari",
        f"- Jumlah kasus terdeteksi: {ringkasan_selisih.get('jumlah_terdeteksi')}",
        f"- Kejadian terlewat: {ringkasan_selisih.get('kejadian_terlewat')}",
        "",
        "## Gerbang Keputusan",
        "",
        f"- Keputusan: **{keputusan_gerbang.get('keputusan')}**",
        f"- Alasan: {keputusan_gerbang.get('alasan')}",
        "",
        "## Catatan Kejujuran",
        "",
        "Akurasi sengaja tidak dihitung di ringkasan ini. Precision@20 pada "
        "potret realistis adalah metrik utama yang dilaporkan.",
    ]

    path.write_text("\n".join(baris), encoding="utf-8")


__all__ = ["tulis_ringkasan_markdown"]
