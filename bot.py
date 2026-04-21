import os
import time
import logging
import asyncio
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIG ---
TELEGRAM_TOKEN = "8285229070:AAGZQnCbjULqMUsZkmNMBSG9NCh3WlI2bNo"
CHAT_ID = "1207682165"
IST = pytz.timezone("Asia/Kolkata")

SYMBOLS = {
    "Nifty 50":  "^NSEI",
    "Sensex":    "^BSESN",
    "BankNifty": "^NSEBANK"
}

is_running = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def check_crossover(symbol_name, ticker):
    try:
        df = yf.download(ticker, period="2d", interval="5m", progress=False)
        if df is None or len(df) < 20:
            return None

        close = df["Close"].squeeze()
        ema9  = calculate_ema(close, 9)
        ema15 = calculate_ema(close, 15)

        prev_9, prev_15 = ema9.iloc[-2], ema15.iloc[-2]
        curr_9, curr_15 = ema9.iloc[-1], ema15.iloc[-1]
        curr_price      = close.iloc[-1]

        now_ist = datetime.now(IST).strftime("%d %b %Y %I:%M %p IST")

        if prev_9 <= prev_15 and curr_9 > curr_15:
            return (
                f"🟢 *BULLISH CROSSOVER*\n"
                f"*{symbol_name}*\n"
                f"Price: ₹{curr_price:.2f}\n"
                f"EMA9: {curr_9:.2f} | EMA15: {curr_15:.2f}\n"
                f"🕐 {now_ist}"
            )

        if prev_9 >= prev_15 and curr_9 < curr_15:
            return (
                f"🔴 *BEARISH CROSSOVER*\n"
                f"*{symbol_name}*\n"
                f"Price: ₹{curr_price:.2f}\n"
                f"EMA9: {curr_9:.2f} | EMA15: {curr_15:.2f}\n"
                f"🕐 {now_ist}"
            )

        return None

    except Exception as e:
        logger.error(f"Error fetching {symbol_name}: {e}")
        return None

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    is_running = True
    await update.message.reply_text(
        "✅ *Alert system is ON*\n"
        "Monitoring Nifty 50, Sensex, BankNifty\n"
        "Checking EMA 9/15 every 5 minutes\n\n"
        "Send /off to stop alerts.",
        parse_mode="Markdown"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    is_running = False
    await update.message.reply_text(
        "🔴 *Alert system is OFF*\n"
        "Send /on to restart.",
        parse_mode="Markdown"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = "✅ ON" if is_running else "🔴 OFF"
    await update.message.reply_text(
        f"Alert system is currently: *{state}*",
        parse_mode="Markdown"
    )

async def scanner_loop(app):
    global is_running
    while True:
        if is_running:
            now_ist = datetime.now(IST)
            if (
                now_ist.weekday() < 5 and
                (9, 15) <= (now_ist.hour, now_ist.minute) <= (15, 30)
            ):
                logger.info(f"Scanning at {now_ist.strftime('%H:%M IST')}")
                for name, ticker in SYMBOLS.items():
                    msg = check_crossover(name, ticker)
                    if msg:
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=msg,
                            parse_mode="Markdown"
                        )
                    await asyncio.sleep(2)
            else:
                logger.info("Outside market hours. Sleeping.")

        await asyncio.sleep(300)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("on",    start_cmd))
    app.add_handler(CommandHandler("off",   stop_cmd))
    app.add_handler(CommandHandler("status",status_cmd))

    asyncio.create_task(scanner_loop(app))

    logger.info("Bot is running...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
