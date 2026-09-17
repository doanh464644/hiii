import logging
import secrets
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, Application
import database

import os
from dotenv import load_dotenv

load_dotenv()

# --- Cấu hình ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_ID")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR else None

if not BOT_TOKEN or not ADMIN_ID:
    print("❌ Lỗi Bảo Mật: Vui lòng thiết lập BOT_TOKEN và ADMIN_ID trong file .env hoặc biến môi trường!")
    exit(1)

# Thiết lập logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def generate_random_key(length=12):
    """Tạo chuỗi key ngẫu nhiên gồm chữ hoa và số"""
    chars = string.ascii_uppercase + string.digits
    return "BONGX-" + "".join(secrets.choice(chars) for _ in range(length))

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

# ── /start ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ <b>Bạn không có quyền sử dụng Bot này.</b>", parse_mode='HTML')
        return

    msg = (
        "👑 <b>BẢNG ĐIỀU KHIỂN BONGX ADMIN</b> 👑\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Các lệnh hỗ trợ:</b>\n\n"
        "🔹 <code>/gen [ngày] [thiết_bị]</code> — Tạo Key mới\n"
        "<i>   (VD: /gen 30 2)</i>\n\n"
        "🔹 <code>/info [key]</code> — Xem chi tiết Key\n"
        "🔹 <code>/list</code> — Danh sách 20 Key gần nhất\n"
        "🔹 <code>/del [key]</code> — Xóa Key khỏi hệ thống\n"
        "🔹 <code>/reset [key]</code> — Reset HWID của Key\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode='HTML')

# ── /gen ───────────────────────────────────────────────────────────────────
async def gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    try:
        days       = int(context.args[0]) if len(context.args) > 0 else 30
        max_dev    = int(context.args[1]) if len(context.args) > 1 else 1
        new_key    = generate_random_key()

        if database.add_key(new_key, days, max_dev):
            msg = (
                "✅ <b>TẠO KEY THÀNH CÔNG</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🔑 <b>Key:</b> <code>{new_key}</code>\n"
                f"⏳ <b>Hạn dùng:</b> {days} ngày\n"
                f"📱 <b>Giới hạn:</b> {max_dev} thiết bị\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Copy key ở trên gửi cho khách hàng nhé!</i>"
            )
            await update.message.reply_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ <b>Lỗi:</b> Không thể lưu Key vào cơ sở dữ liệu.", parse_mode='HTML')

    except (ValueError, IndexError):
        await update.message.reply_text(
            "⚠️ <b>Sai cú pháp. Ví dụ:</b>\n\n"
            "<code>/gen 30</code> — 30 ngày, 1 thiết bị\n"
            "<code>/gen 30 3</code> — 30 ngày, 3 thiết bị",
            parse_mode='HTML'
        )

# ── /list ──────────────────────────────────────────────────────────────────
async def list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    keys = database.list_keys()
    if not keys:
        await update.message.reply_text("📭 <b>Danh sách Key hiện tại đang trống.</b>", parse_mode='HTML')
        return

    msg = "📋 <b>DANH SÁCH 20 KEY GẦN NHẤT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key_str, active_dev, max_dev, expiry in keys:
        is_expired = expiry < __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "🔴" if is_expired else ("🟡" if active_dev >= max_dev else "🟢")
        msg += (
            f"{status_icon} <code>{key_str}</code>\n"
            f"      ├─ 📱 {active_dev}/{max_dev} thiết bị\n"
            f"      └─ 📅 {expiry[:10]}\n\n"
        )

    await update.message.reply_text(msg, parse_mode='HTML')

# ── /info ──────────────────────────────────────────────────────────────────
async def info_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Vui lòng nhập Key.</b> \nVí dụ: <code>/info BONGX-XXXX</code>", parse_mode='HTML')
        return

    info = database.get_key_info(context.args[0])
    if not info:
        await update.message.reply_text("❌ <b>Không tìm thấy Key này.</b>", parse_mode='HTML')
        return

    devices_text = ""
    if info["devices"]:
        for i, (hwid, reg_at) in enumerate(info["devices"], 1):
            devices_text += f"      ├─ 💻 Máy {i}: <code>{hwid[:10]}...</code>\n      └─ 📅 {reg_at}\n"
    else:
        devices_text = "      └─ <i>(Chưa có thiết bị nào)</i>\n"

    msg = (
        "🔍 <b>CHI TIẾT KEY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>Key:</b> <code>{info['key']}</code>\n"
        f"📅 <b>Tạo lúc:</b> {info['created_at'][:10]}\n"
        f"⏳ <b>Hết hạn:</b> {info['expiry'][:10]}\n"
        f"📱 <b>Thiết bị:</b> {len(info['devices'])}/{info['max_devices']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Danh sách thiết bị:</b>\n"
        f"{devices_text}"
    )

    # Nút nhanh Xóa key / Reset HWID
    keyboard = [
        [
            InlineKeyboardButton("🗑 Xóa Key", callback_data=f"del|{info['key']}"),
            InlineKeyboardButton("🔄 Reset HWID", callback_data=f"reset|{info['key']}"),
        ]
    ]
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# ── /del ───────────────────────────────────────────────────────────────────
async def del_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Vui lòng nhập Key.</b> \nVí dụ: <code>/del BONGX-XXXX</code>", parse_mode='HTML')
        return

    key_to_del = context.args[0]

    # Nút xác nhận tránh xóa nhầm
    keyboard = [[
        InlineKeyboardButton("✅ Xác nhận Xóa", callback_data=f"del|{key_to_del}"),
        InlineKeyboardButton("❌ Hủy", callback_data="cancel"),
    ]]
    await update.message.reply_text(
        f"⚠️ <b>Bạn có chắc muốn xóa key:</b>\n<code>{key_to_del}</code>?",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── /reset ─────────────────────────────────────────────────────────────────
async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ <b>Vui lòng nhập Key.</b> \nVí dụ: <code>/reset BONGX-XXXX</code>", parse_mode='HTML')
        return

    key_to_reset = context.args[0]
    if database.reset_hwid(key_to_reset):
        await update.message.reply_text(
            f"✅ <b>Đã reset tất cả HWID cho Key:</b>\n<code>{key_to_reset}</code>\n\n"
            f"<i>Khách có thể đăng nhập trên thiết bị mới.</i>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(f"❌ Không tìm thấy Key <code>{key_to_reset}</code>.", parse_mode='HTML')

# ── Callback từ nút Inline ────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ <b>Không có quyền.</b>", parse_mode='HTML')
        return

    data = query.data

    if data == "cancel":
        await query.edit_message_text("❎ <b>Đã hủy thao tác.</b>", parse_mode='HTML')
        return

    action, key_str = data.split("|", 1)

    if action == "del":
        if database.delete_key(key_str):
            await query.edit_message_text(f"🗑 <b>Đã xóa Key</b> <code>{key_str}</code> khỏi hệ thống.", parse_mode='HTML')
        else:
            await query.edit_message_text(f"❌ Không tìm thấy Key <code>{key_str}</code> để xóa.", parse_mode='HTML')

    elif action == "reset":
        database.reset_hwid(key_str)
        await query.edit_message_text(
            f"🔄 <b>Đã reset HWID cho Key</b> <code>{key_str}</code>.\n<i>Khách có thể đăng nhập trên thiết bị mới.</i>",
            parse_mode='HTML'
        )

# ── Thiết lập Menu Gợi Ý Lệnh ──────────────────────────────────────────────
async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "👋 Hiện Menu Hỗ Trợ & Hướng dẫn"),
        BotCommand("gen", "🔑 Tạo Key mới (VD: /gen 30 1)"),
        BotCommand("list", "📋 Xem danh sách 20 Key gần nhất"),
        BotCommand("info", "🔍 Xem chi tiết Key & Thiết bị"),
        BotCommand("reset", "🔄 Reset HWID cho Key"),
        BotCommand("del", "🗑 Xóa Key khỏi hệ thống"),
    ])
    print("✅ Đã cập nhật Menu Gợi ý lệnh trên Telegram!")

# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("🤖 Bot BONGX đang khởi động...")
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('gen',   gen_key))
    application.add_handler(CommandHandler('list',  list_keys))
    application.add_handler(CommandHandler('info',  info_key))
    application.add_handler(CommandHandler('del',   del_key))
    application.add_handler(CommandHandler('reset', reset_key))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("✅ Bot đã sẵn sàng!")
    application.run_polling()
