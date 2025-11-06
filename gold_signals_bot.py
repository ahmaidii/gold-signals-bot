# gold_signals_bot.py
# Telegram bot: gold signals + periodic broadcast to subscribers every N minutes.
# Requirements: python-telegram-bot==13.15

import os
import json
import random
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
PRICES_FILE = "prices.json"
SUBSCRIBERS_FILE = "subscribers.json"
SYMBOL = "XAUUSD"
BROADCAST_INTERVAL_MIN = int(os.getenv("BROADCAST_INTERVAL_MIN", "30"))

def load_json_file(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json_file(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
    except Exception:
        pass

def load_prices():
    return load_json_file(PRICES_FILE, [])

def save_prices(lst):
    save_json_file(PRICES_FILE, lst[-500:])

def load_subscribers():
    data = load_json_file(SUBSCRIBERS_FILE, [])
    try:
        return set(int(x) for x in data)
    except Exception:
        return set()

def save_subscribers(s):
    save_json_file(SUBSCRIBERS_FILE, list(s))

def sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period

def get_price():
    prices = load_prices()
    base = prices[-1] if prices else 2000.0
    new_price = round(base + random.uniform(-4, 4), 2)
    prices.append(new_price)
    save_prices(prices)
    return new_price

def generate_signal():
    prices = load_prices()
    price = get_price()
    sma5 = sma(prices, 5)
    sma20 = sma(prices, 20)
    if sma5 and sma20:
        if sma5 > sma20:
            side = "BUY"
        elif sma5 < sma20:
            side = "SELL"
        else:
            side = "HOLD"
    else:
        side = random.choice(["BUY", "SELL"])
    confidence = round(random.uniform(0.6, 0.9), 2)
    sl = round(price * (0.995 if side == "BUY" else 1.005), 2)
    tp = round(price * (1.02 if side == "BUY" else 0.98), 2)
    return {"side": side, "price": price, "confidence": confidence, "sl": sl, "tp": tp, "generated_at": datetime.utcnow().isoformat() + "Z"}

def build_signal_text(sig):
    lines = [f"📊 إشارة {SYMBOL}", f"النوع: {sig['side']}", f"السعر: {sig['price']} USD"]
    lines.append(f"الثقة: {int(sig['confidence']*100)}%")
    lines.append(f"وقف خسارة (SL): {sig['sl']}")
    lines.append(f"هدف ربح (TP): {sig['tp']}")
    lines.append(f"وقت التوليد: {sig['generated_at']}")
    return "\\n".join(lines)

def start(update: Update, context: CallbackContext):
    msg = (
        "مرحباً! بوت إشارات الذهب 🟡\\n"
        f"الأوامر:\\n"
        "/signal - احصل على إشارة جديدة الآن\\n"
        f"/subscribe - الاشتراك في البث التلقائي كل {BROADCAST_INTERVAL_MIN} دقيقة\\n"
        "/unsubscribe - إلغاء الاشتراك\\n"
        "/help - تعليمات\\n"
        "ملاحظة: هذا بوت تعليمي. الإشارات ليست توصية استثمارية."
    )
    update.message.reply_text(msg)

def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("/signal, /subscribe, /unsubscribe")

def signal_cmd(update: Update, context: CallbackContext):
    sig = generate_signal()
    update.message.reply_text(build_signal_text(sig))

def subscribe_cmd(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    subs.add(chat_id)
    save_subscribers(subs)
    update.message.reply_text(f"✅ تم الاشتراك في البث التلقائي. ستتلقى إشارات كل {BROADCAST_INTERVAL_MIN} دقيقة.")

def unsubscribe_cmd(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
        update.message.reply_text("✅ تم إلغاء الاشتراك.")
    else:
        update.message.reply_text("أنت غير مشترك بالفعل.")

def broadcast_job(context: CallbackContext):
    sig = generate_signal()
    if sig["side"] not in ("BUY", "SELL"):
        print(f"[{datetime.utcnow().isoformat()}] Generated HOLD — skipping broadcast.")
        return
    text = build_signal_text(sig)
    subs = load_subscribers()
    if not subs:
        print("No subscribers to broadcast to.")
        return
    for chat_id in subs:
        try:
            context.bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            print("Failed to send to", chat_id, e)

def main():
    if not TG_BOT_TOKEN:
        print("❌ ضع TG_BOT_TOKEN في البيئة (Render Environment Variables).")
        return
    updater = Updater(TG_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("signal", signal_cmd))
    dp.add_handler(CommandHandler("subscribe", subscribe_cmd))
    dp.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    dp.add_handler(MessageHandler(Filters.command, lambda u, c: u.message.reply_text("أمر غير معروف. استخدم /help.")))

    interval_seconds = max(60, BROADCAST_INTERVAL_MIN * 60)
    job_queue = updater.job_queue
    job_queue.run_repeating(broadcast_job, interval=interval_seconds, first=interval_seconds)

    print(f"✅ البوت يعمل الآن. البث كل {BROADCAST_INTERVAL_MIN} دقيقة.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
