# Bot Telegram - Rekap Uang Jajan
### Fitur:
  - /start, /help
  - Catat pemasukan : /masuk <jumlah> <kategori> <keterangan>
  - Catat pengeluaran: /keluar <jumlah> <kategori> <keterangan>
  - Rekap            : /rekap harian | mingguan | bulanan | tahunan
  - Kategori         : /kategori  — lihat daftar kategori
  - Set budget       : /setbudget <kategori> <jumlah>
  - Cek budget       : /budget
  - exportcsv        : download semua transaksi dalam CSV
  - Notif otomatis   : aktif tiap malam jam 21.00 (daftar dulu via /mulainotif)
  - Hapus semua data : /reset

### Depedency:
    pip install python-telegram-bot python-dotenv

### Running Program:
    python bot.py

