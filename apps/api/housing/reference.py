"""Programme facts shown next to prices. Each carries its source; update them when the rules do.

These apply to landed subsidized houses (rumah tapak) in West Java outside Bogor, Depok and
Bekasi, which covers every area this dataset has.
"""

# Newest first. A listing priced at an older ceiling was most likely entered back then and
# never updated: the developer sells at whatever ceiling is in force on the day of signing.
PRICE_CEILINGS = [
    {
        "price_idr": 166_000_000,
        "period": "sejak 2024",
        "basis": "Kepmen PUPR 689/KPTS/M/2023, masih berlaku pada 2026",
    },
    {"price_idr": 162_000_000, "period": "2023", "basis": "Kepmen PUPR 689/KPTS/M/2023"},
    {"price_idr": 150_500_000, "period": "sebelum Juni 2023", "basis": "batas harga sebelumnya"},
]

CURRENT_CEILING_IDR = PRICE_CEILINGS[0]["price_idr"]

# KPR FLPP for landed houses. The 40-year tenor was approved in June 2026; banks were still
# rolling it out later that year, so 20 years stays the default here.
KPR = {
    "annual_rate": 0.05,
    "min_down_payment": 0.01,
    "tenor_years": [10, 15, 20, 30, 40],
    "default_tenor_years": 20,
}

SOURCES = [
    {
        "topic": "Batas harga jual rumah subsidi",
        "title": "Harga Rumah Subsidi Diusulkan Naik di 2026, Cek Daftar yang Berlaku Saat Ini",
        "publisher": "Bisnis.com, 4 Januari 2026",
        "url": "https://ekonomi.bisnis.com/read/20260104/47/1941442/harga-rumah-subsidi-diusulkan-naik-di-2026-cek-daftar-yang-berlaku-saat-ini",
    },
    {
        "topic": "Tenor KPR subsidi hingga 40 tahun, bunga tetap 5%",
        "title": "Resmi! Tenor KPR Rumah Subsidi & Rusun Diperpanjang Sampai 40 Tahun",
        "publisher": "Bisnis.com, 25 Juni 2026",
        "url": "https://ekonomi.bisnis.com/read/20260625/47/1983246/resmi-tenor-kpr-rumah-subsidi-rusun-diperpanjang-sampai-40-tahun",
    },
    {
        "topic": "Akad KPR FLPP hanya untuk rumah siap huni",
        "title": "Akad Kredit FLPP hanya Boleh Dilakukan saat Rumah Siap Huni",
        "publisher": "Metrotvnews.com",
        "url": "https://www.metrotvnews.com/read/N4EC4YrG-akad-kredit-flpp-hanya-boleh-dilakukan-saat-rumah-siap-huni",
    },
    {
        "topic": "Arti jumlah unit di Sikumbang",
        "title": "Tutorial Mencari Rumah Lewat Laman SiKumbang",
        "publisher": "detikJabar, Februari 2026",
        "url": "https://www.detik.com/jabar/berita/d-8349563/tutorial-mencari-rumah-lewat-laman-sikumbang",
    },
]
