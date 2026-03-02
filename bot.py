import json
import csv
import asyncio
import os
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

load_dotenv()

TOKEN     = os.environ.get("BOT_TOKEN", "ISI_TOKEN_BOT_KAMU_DI_SINI")
DATA_FILE = "data_keuangan.json"
KATEGORI_DEFAULT = ["makanan", "transportasi", "hiburan", "kesehatan", "belanja", "tagihan", "gaji", "assets", "lainnya"]

# ── Utilitas Data ─────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"transaksi": [], "budget": {}, "notif": False}
    if isinstance(data[uid], list):
        data[uid] = {"transaksi": data[uid], "budget": {}, "notif": False}
    return data[uid]

def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

def tambah_transaksi(user_id, tipe, jumlah, kategori, keterangan):
    data = load_data()
    user = get_user(data, user_id)
    user["transaksi"].append({
        "tipe"      : tipe,
        "jumlah"    : jumlah,
        "kategori"  : kategori.lower(),
        "keterangan": keterangan,
        "tanggal"   : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_data(data)
    if tipe == "keluar":
        return cek_budget_warning(user_id, kategori.lower())
    return None

def cek_budget_warning(user_id, kategori):
    data   = load_data()
    user   = get_user(data, user_id)
    budget = user["budget"].get(kategori)
    if not budget:
        return None
    now   = datetime.now()
    batas = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_keluar = sum(
        t["jumlah"] for t in user["transaksi"]
        if t["tipe"] == "keluar"
        and t["kategori"] == kategori
        and datetime.strptime(t["tanggal"], "%Y-%m-%d %H:%M:%S") >= batas
    )
    persen = (total_keluar / budget) * 100
    if persen >= 100:
        return f"🚨 *BUDGET {kategori.upper()} HABIS!*\nPengeluaran {format_rupiah(total_keluar)} dari budget {format_rupiah(budget)}."
    elif persen >= 80:
        return f"⚠️ *Peringatan budget {kategori}!*\nSudah terpakai {persen:.0f}% ({format_rupiah(total_keluar)} dari {format_rupiah(budget)})."
    return None

def rekap_transaksi(user_id, periode):
    data      = load_data()
    user      = get_user(data, user_id)
    transaksi = user["transaksi"]
    now       = datetime.now()

    if periode == "harian":
        batas = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"Hari ini ({now.strftime('%d %B %Y')})"
    elif periode == "mingguan":
        batas = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"Minggu ini ({batas.strftime('%d %b')} - {now.strftime('%d %b %Y')})"
    elif periode == "bulanan":
        batas = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = f"Bulan ini ({now.strftime('%B %Y')})"
    elif periode == "tahunan":
        batas = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        label = f"Tahun ini ({now.year})"
    else:
        return "Periode tidak valid. Gunakan: harian | mingguan | bulanan | tahunan"

    filtered = [
        t for t in transaksi
        if datetime.strptime(t["tanggal"], "%Y-%m-%d %H:%M:%S") >= batas
    ]
    if not filtered:
        return f"📊 *Rekap {label}*\n\nBelum ada transaksi."

    total_masuk  = sum(t["jumlah"] for t in filtered if t["tipe"] == "masuk")
    total_keluar = sum(t["jumlah"] for t in filtered if t["tipe"] == "keluar")
    saldo        = total_masuk - total_keluar

    kategori_map = {}
    for t in filtered:
        if t["tipe"] == "keluar":
            k = t.get("kategori", "lainnya")
            kategori_map[k] = kategori_map.get(k, 0) + t["jumlah"]

    detail_kategori = "\n".join(
        f"  • {k.capitalize()}: {format_rupiah(v)}"
        for k, v in sorted(kategori_map.items(), key=lambda x: -x[1])
    ) or "  (tidak ada)"

    detail_masuk = "\n".join(
        f"  + [{t.get('kategori','—')}] {t['keterangan']} — {format_rupiah(t['jumlah'])}"
        for t in filtered if t["tipe"] == "masuk"
    ) or "  (tidak ada)"

    detail_keluar = "\n".join(
        f"  - [{t.get('kategori','—')}] {t['keterangan']} — {format_rupiah(t['jumlah'])}"
        for t in filtered if t["tipe"] == "keluar"
    ) or "  (tidak ada)"

    return (
        f"📊 *Rekap {label}*\n\n"
        f"💰 *Pemasukan:*\n{detail_masuk}\n"
        f"  *Total: {format_rupiah(total_masuk)}*\n\n"
        f"💸 *Pengeluaran:*\n{detail_keluar}\n"
        f"  *Total: {format_rupiah(total_keluar)}*\n\n"
        f"🗂️ *Per Kategori:*\n{detail_kategori}\n\n"
        f"{'🟢' if saldo >= 0 else '🔴'} *Saldo: {format_rupiah(saldo)}*"
    )

def export_transaksi_csv(user_id):
    data = load_data()
    user = get_user(data, user_id)
    transaksi = user["transaksi"]

    if not transaksi:
        return None

    filename = f"transaksi_{user_id}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Tanggal",
            "Tipe",
            "Kategori",
            "Keterangan",
            "Jumlah"
        ])

        for t in transaksi:
            writer.writerow([
                t["tanggal"],
                t["tipe"],
                t["kategori"],
                t["keterangan"],
                t["jumlah"]
            ])

    return filename
# ── Notifikasi Otomatis ───────────────────────────────────────────────────────
async def kirim_notif_malam(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    for uid, user in data.items():
        if isinstance(user, dict) and user.get("notif"):
            hasil = rekap_transaksi(int(uid), "harian")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"🌙 *Ringkasan Harianmu*\n\n{hasil}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


# ── Handler Command ───────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.effective_user.first_name
    pesan = (
        f"Halo, *{nama}*! 👋\n\n"
        "Aku Serrie pencatat uang jajanmu.\n\n"
        "➕ `/masuk <jumlah> <kategori> <keterangan>`\n"
        "   Contoh: `/masuk 50000 lainnya uang saku`\n\n"
        "➖ `/keluar <jumlah> <kategori> <keterangan>`\n"
        "   Contoh: `/keluar 15000 makanan makan siang`\n\n"
        "📊 `/rekap harian | mingguan | bulanan | tahunan`\n"
        "📊 `/exportcsv - export keuangan ke csv`\n"
        "🏷️ `/kategori` — lihat daftar kategori\n"
        "🎯 `/setbudget <kategori> <jumlah>` — set batas budget\n"
        "💼 `/budget` — cek sisa budget bulan ini\n"
        "🔔 `/mulainotif` — aktifkan ringkasan tiap malam jam 21.00\n"
        "🔕 `/stopnotif` — matikan notifikasi\n"
        "🗑️ `/reset` — hapus semua data\n"
        "❓ `/help` — tampilkan panduan ini"
    )
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def kategori_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    daftar = "\n".join(f"  • `{k}`" for k in KATEGORI_DEFAULT)
    await update.message.reply_text(
        f"🏷️ *Daftar Kategori:*\n{daftar}\n\nKamu bisa pakai kategori lain juga, bebas!",
        parse_mode="Markdown"
    )

async def masuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ Format: `/masuk <jumlah> <kategori> <keterangan>`\n"
            "Contoh: `/masuk 50000 lainnya uang saku`\n\nLihat kategori: /kategori",
            parse_mode="Markdown"
        )
        return
    try:
        jumlah     = float(args[0].replace(".", "").replace(",", ""))
        kategori   = args[1]
        keterangan = " ".join(args[2:])
        tambah_transaksi(update.effective_user.id, "masuk", jumlah, kategori, keterangan)
        await update.message.reply_text(
            f"✅ *Pemasukan dicatat!*\n💰 {format_rupiah(jumlah)} — {keterangan} [{kategori}]",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("⚠️ Jumlah harus angka.", parse_mode="Markdown")

async def keluar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ Format: `/keluar <jumlah> <kategori> <keterangan>`\n"
            "Contoh: `/keluar 15000 makanan makan siang`\n\nLihat kategori: /kategori",
            parse_mode="Markdown"
        )
        return
    try:
        jumlah     = float(args[0].replace(".", "").replace(",", ""))
        kategori   = args[1]
        keterangan = " ".join(args[2:])
        warning    = tambah_transaksi(update.effective_user.id, "keluar", jumlah, kategori, keterangan)
        await update.message.reply_text(
            f"🔴 *Pengeluaran dicatat!*\n💸 {format_rupiah(jumlah)} — {keterangan} [{kategori}]",
            parse_mode="Markdown"
        )
        if warning:
            await update.message.reply_text(warning, parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("⚠️ Jumlah harus angka.", parse_mode="Markdown")

async def setbudget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Format: `/setbudget <kategori> <jumlah>`\nContoh: `/setbudget makanan 300000`",
            parse_mode="Markdown"
        )
        return
    try:
        kategori = args[0].lower()
        jumlah   = float(args[1].replace(".", "").replace(",", ""))
        data     = load_data()
        user     = get_user(data, update.effective_user.id)
        user["budget"][kategori] = jumlah
        save_data(data)
        await update.message.reply_text(
            f"🎯 *Budget {kategori} diset!*\nLimit: {format_rupiah(jumlah)} / bulan",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("⚠️ Jumlah harus angka.", parse_mode="Markdown")

async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data   = load_data()
    user   = get_user(data, update.effective_user.id)
    budget = user.get("budget", {})
    if not budget:
        await update.message.reply_text(
            "Belum ada budget. Gunakan `/setbudget <kategori> <jumlah>` untuk mulai.",
            parse_mode="Markdown"
        )
        return
    now   = datetime.now()
    batas = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    baris = []
    for kategori, limit in budget.items():
        terpakai = sum(
            t["jumlah"] for t in user["transaksi"]
            if t["tipe"] == "keluar"
            and t.get("kategori") == kategori
            and datetime.strptime(t["tanggal"], "%Y-%m-%d %H:%M:%S") >= batas
        )
        sisa   = limit - terpakai
        persen = (terpakai / limit) * 100
        emoji  = "🟢" if persen < 80 else ("🟡" if persen < 100 else "🔴")
        baris.append(
            f"{emoji} *{kategori.capitalize()}*\n"
            f"   Terpakai: {format_rupiah(terpakai)} / {format_rupiah(limit)} ({persen:.0f}%)\n"
            f"   Sisa: {format_rupiah(max(sisa, 0))}"
        )
    await update.message.reply_text("💼 *Budget Bulan Ini:*\n\n" + "\n\n".join(baris), parse_mode="Markdown")

async def rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Gunakan: `/rekap harian | mingguan | bulanan | tahunan`",
            parse_mode="Markdown"
        )
        return
    hasil = rekap_transaksi(update.effective_user.id, context.args[0].lower())
    await update.message.reply_text(hasil, parse_mode="Markdown")

async def exportcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    filename = export_transaksi_csv(user_id)

    if not filename:
        await update.message.reply_text("Belum ada transaksi untuk diexport.")
        return

    with open(filename, "rb") as file:
        await update.message.reply_document(
            document=file,
            filename=filename,
            caption="📁 Berikut data transaksi kamu dalam format CSV."
        )

async def mulai_notif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = get_user(data, update.effective_user.id)
    user["notif"] = True
    save_data(data)
    await update.message.reply_text(
        "🔔 Notifikasi *aktif!*\nKamu akan dapat ringkasan harian tiap malam jam 21.00 WIB.",
        parse_mode="Markdown"
    )

async def stop_notif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = get_user(data, update.effective_user.id)
    user["notif"] = False
    save_data(data)
    await update.message.reply_text("🔕 Notifikasi dimatikan.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid  = str(update.effective_user.id)
    if uid in data:
        data[uid] = {"transaksi": [], "budget": {}, "notif": False}
        save_data(data)
    await update.message.reply_text("🗑️ Semua data transaksimu udah dihapus.")

async def balas_otomatis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text.lower()
    if any(k in teks for k in ["halo", "hai", "hello", "hi"]):
        await update.message.reply_text(f"Halo juga, {update.effective_user.first_name}!, Aku Serrie asisten keuanganmu 😊. Ketik /help biar aku bisa bantu kamu!.")
    elif "terima kasih" in teks or "makasih" in teks:
        await update.message.reply_text("Sama-sama! 😊")
    elif "saldo" in teks:
        await update.message.reply_text("buat cek saldo, kamu bisa pake /rekap harian 📊")
    elif "budget" in teks:
        await update.message.reply_text("buat cek budget, kamu bisa pake /budget 💼")
    else:
        await update.message.reply_text("Hmm, aku kurang paham. Coba ketik /help buat lihat daftar perintahnya deh! 😊")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       help_command))
    app.add_handler(CommandHandler("kategori",   kategori_command))
    app.add_handler(CommandHandler("masuk",      masuk))
    app.add_handler(CommandHandler("keluar",     keluar))
    app.add_handler(CommandHandler("setbudget",  setbudget))
    app.add_handler(CommandHandler("budget",     budget_command))
    app.add_handler(CommandHandler("rekap",      rekap))
    app.add_handler(CommandHandler("exportcsv", exportcsv))
    app.add_handler(CommandHandler("mulainotif", mulai_notif))
    app.add_handler(CommandHandler("stopnotif",  stop_notif))
    app.add_handler(CommandHandler("reset",      reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, balas_otomatis))

    # Notifikasi tiap hari jam 21.00 WIB (= 14.00 UTC)
    app.job_queue.run_daily(
        kirim_notif_malam,
        time=time(hour=14, minute=0, second=0)
    )

    print("🤖 Bot berjalan... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()