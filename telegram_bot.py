import logging
import secrets
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, Application
import database

# --- Cấu hình ---
BOT_TOKEN = "8645812017:AAEZJOOZriGDXMbMTUk0p8kJFI1J95DONKs"
ADMIN_ID = 7509896689

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
        await update.message.reply_text("❌ Bạn không có quyền sử dụng Bot này.")
        return

    msg = (
        "👋 *Chào mừng Admin BONGX!*\n\n"
        "Các lệnh hỗ trợ:\n"
        "🔹 `/gen [ngày] [max_thiết_bị]` — Tạo Key mới\n"
        "   Ví dụ: `/gen 30 2` (30 ngày, tối đa 2 thiết bị)\n"
        "🔹 `/del [key]` — Xóa Key khỏi hệ thống\n"
        "🔹 `/list` — Liệt kê 20 Key gần nhất\n"
        "🔹 `/info [key]` — Xem chi tiết Key & thiết bị\n"
        "🔹 `/reset [key]` — Reset toàn bộ HWID của Key\n"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# ── /gen ───────────────────────────────────────────────────────────────────
async def gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    try:
        days       = int(context.args[0]) if len(context.args) > 0 else 30
        max_dev    = int(context.args[1]) if len(context.args) > 1 else 1
        new_key    = generate_random_key()

        if database.add_key(new_key, days, max_dev):
            await update.message.reply_text(
                f"✅ *Tạo Key thành công!*\n\n"
                f"🔑 Key: `{new_key}`\n"
                f"⏳ Hạn dùng: *{days} ngày*\n"
                f"📱 Giới hạn thiết bị: *{max_dev} thiết bị*\n\n"
                f"_Copy key này gửi cho khách hàng._",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Lỗi: Không thể lưu Key vào cơ sở dữ liệu.")

    except (ValueError, IndexError):
        await update.message.reply_text(
            "⚠️ Sai cú pháp. Ví dụ:\n"
            "`/gen 30` — 30 ngày, 1 thiết bị\n"
            "`/gen 30 3` — 30 ngày, 3 thiết bị",
            parse_mode='Markdown'
        )

# ── /list ──────────────────────────────────────────────────────────────────
async def list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    keys = database.list_keys()
    if not keys:
        await update.message.reply_text("📭 Danh sách Key hiện tại đang trống.")
        return

    msg = "📋 *Danh sách 20 Key gần nhất:*\n\n"
    for key_str, active_dev, max_dev, expiry in keys:
        is_expired = expiry < __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "🔴" if is_expired else ("🟡" if active_dev >= max_dev else "🟢")
        msg += (
            f"{status_icon} `{key_str}`\n"
            f"   📱 {active_dev}/{max_dev} thiết bị  |  📅 {expiry[:10]}\n\n"
        )

    await update.message.reply_text(msg, parse_mode='Markdown')

# ── /info ──────────────────────────────────────────────────────────────────
async def info_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập Key. Ví dụ: `/info BONGX-XXXX`", parse_mode='Markdown')
        return

    info = database.get_key_info(context.args[0])
    if not info:
        await update.message.reply_text("❌ Không tìm thấy Key này.")
        return

    devices_text = ""
    if info["devices"]:
        for i, (hwid, reg_at) in enumerate(info["devices"], 1):
            devices_text += f"   {i}. `{hwid[:16]}...`\n      📅 {reg_at}\n"
    else:
        devices_text = "   _(Chưa có thiết bị nào)_\n"

    msg = (
        f"🔍 *Chi tiết Key:*\n\n"
        f"🔑 `{info['key']}`\n"
        f"📅 Tạo lúc: {info['created_at'][:10]}\n"
        f"⏳ Hết hạn: {info['expiry'][:10]}\n"
        f"📱 Thiết bị: {len(info['devices'])}/{info['max_devices']}\n\n"
        f"*Danh sách thiết bị đã đăng ký:*\n"
        f"{devices_text}"
    )

    # Nút nhanh Xóa key / Reset HWID
    keyboard = [
        [
            InlineKeyboardButton("🗑 Xóa Key", callback_data=f"del|{info['key']}"),
            InlineKeyboardButton("🔄 Reset HWID", callback_data=f"reset|{info['key']}"),
        ]
    ]
    await update.message.reply_text(msg, parse_mode='Markdown',
                                    reply_markup=InlineKeyboardMarkup(keyboard))

# ── /del ───────────────────────────────────────────────────────────────────
async def del_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập Key. Ví dụ: `/del BONGX-XXXX`", parse_mode='Markdown')
        return

    key_to_del = context.args[0]

    # Nút xác nhận tránh xóa nhầm
    keyboard = [[
        InlineKeyboardButton("✅ Xác nhận Xóa", callback_data=f"del|{key_to_del}"),
        InlineKeyboardButton("❌ Hủy", callback_data="cancel"),
    ]]
    await update.message.reply_text(
        f"⚠️ Bạn có chắc muốn xóa key:\n`{key_to_del}`?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── /reset ─────────────────────────────────────────────────────────────────
async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    if not context.args:
        await update.message.reply_text("⚠️ Vui lòng nhập Key. Ví dụ: `/reset BONGX-XXXX`", parse_mode='Markdown')
        return

    key_to_reset = context.args[0]
    if database.reset_hwid(key_to_reset):
        await update.message.reply_text(
            f"✅ Đã reset tất cả HWID cho Key:\n`{key_to_reset}`\n\n"
            f"_Khách có thể đăng nhập trên thiết bị mới._",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Không tìm thấy Key `{key_to_reset}`.")

# ── Callback từ nút Inline ────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Không có quyền.")
        return

    data = query.data

    if data == "cancel":
        await query.edit_message_text("❎ Đã hủy thao tác.")
        return

    action, key_str = data.split("|", 1)

    if action == "del":
        if database.delete_key(key_str):
            await query.edit_message_text(f"🗑 Đã xóa Key `{key_str}` khỏi hệ thống.", parse_mode='Markdown')
        else:
            await query.edit_message_text(f"❌ Không tìm thấy Key `{key_str}` để xóa.")

    elif action == "reset":
        database.reset_hwid(key_str)
        await query.edit_message_text(
            f"🔄 Đã reset HWID cho Key `{key_str}`.\n_Khách có thể đăng nhập trên thiết bị mới._",
            parse_mode='Markdown'
        )

# ── Thiết lập Menu Gợi Ý Lệnh ──────────────────────────────────────────────
async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "👋 Hiện Menu Hỗ Trợ & Hướng dẫn"),
        BotCommand("gen", "🔑 Tạo Key mới (VD: /gen 30 1)"),
        BotCommand("list", "📋 Xem danh sách 20 Key gần nhất"),
        BotCommand("info", "🔍 Xem chi tiết Key & Thiết bị (VD: /info BONGX-...)"),
        BotCommand("reset", "🔄 Reset HWID cho Key (VD: /reset BONGX-...)"),
        BotCommand("del", "🗑 Xóa Key khỏi hệ thống (VD: /del BONGX-...)"),
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
