import telebot
import requests
import re
import json
import threading
import time
from datetime import datetime
import urllib.parse
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ===== НАСТРОЙКИ =====
TOKEN = "8394148154:AAE_5bdZYtdFsQTIfxGE5EydI0O9OLU5vJU"
BOT_USERNAME = "TREYD_GPPROJECT_bot"
STEAM_COMMISSION = 0.13
CHECK_INTERVAL = 600
ITEMS_FILE = "items.json"
# =====================

bot = telebot.TeleBot(TOKEN)

# ---------- Работа с файлом ----------
def load_items():
    try:
        with open(ITEMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_items(items):
    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ---------- Получение цен ----------
def get_steam_price(item_name):
    encoded = urllib.parse.quote(item_name)
    url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={encoded}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None, None
        data = r.json()
        if not data.get("success"):
            return None, None
        lowest = data.get("lowest_price")
        if not lowest:
            return None, None
        sell_match = re.search(r'\$([0-9,\.]+)', lowest)
        if not sell_match:
            return None, None
        sell = float(sell_match.group(1).replace(',', ''))
        median = data.get("median_price")
        if median:
            buy_match = re.search(r'\$([0-9,\.]+)', median)
            buy = float(buy_match.group(1).replace(',', '')) if buy_match else sell * 0.85
        else:
            buy = sell * 0.85
        return sell, buy
    except Exception:
        return None, None

# ---------- Реферальная система (сохраняется в items.json) ----------
def get_referral_count(user_id):
    items = load_items()
    for item in items:
        if item.get("type") == "referral" and item.get("user_id") == user_id:
            return item.get("count", 0)
    return 0

def add_referral(user_id, referrer_id):
    items = load_items()
    # Увеличиваем счётчик пригласившего
    found = False
    for item in items:
        if item.get("type") == "referral" and item.get("user_id") == referrer_id:
            item["count"] = item.get("count", 0) + 1
            found = True
            break
    if not found:
        items.append({"type": "referral", "user_id": referrer_id, "count": 1})
    # Запоминаем, что этот пользователь был приглашён
    items.append({"type": "referred", "user_id": user_id, "referrer": referrer_id})
    save_items(items)

def was_referred(user_id):
    items = load_items()
    for item in items:
        if item.get("type") == "referred" and item.get("user_id") == user_id:
            return True
    return False

# ---------- Меню ----------
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🔥 Популярные"),
        KeyboardButton("📋 Мои скины"),
        KeyboardButton("🔗 Рефералка"),
        KeyboardButton("🔍 Проверить скин"),
        KeyboardButton("➕ Добавить скин"),
        KeyboardButton("🧮 Калькулятор")
    )
    return markup

# ---------- ОСНОВНЫЕ КОМАНДЫ (объявлены до общего обработчика) ----------

# ------------------ /start ------------------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    args = message.text.split()
    # Обработка реферального перехода
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id != user_id and not was_referred(user_id):
                add_referral(user_id, referrer_id)
                bot.reply_to(message, "✅ Ты перешёл по реферальной ссылке! Спасибо.")
        except:
            pass
    # Приветствие с меню
    bot.send_message(
        message.chat.id,
        "<b>🤖 CS2 Трейдинг Бот</b>\n\n"
        "Используй кнопки ниже или команды:\n"
        "/add <название>\n"
        "/check <название>\n"
        "/calc <название> <число>\n"
        "/popular\n"
        "/referral\n"
        "/list\n"
        "/remove <номер>",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

# ------------------ /referral ------------------
@bot.message_handler(commands=['referral'])
def referral_command(message):
    user_id = message.from_user.id
    count = get_referral_count(user_id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    bot.send_message(
        message.chat.id,
        f"🔗 <b>Твоя реферальная ссылка:</b>\n{link}\n\nПриглашено друзей: {count}",
        parse_mode="HTML"
    )

# ------------------ /popular ------------------
POPULAR_SKINS = [
    "AK-47 | Redline (Field-Tested)",
    "AWP | Asiimov (Field-Tested)",
    "M4A1-S | Hyper Beast (Minimal Wear)",
    "Desert Eagle | Code Red (Minimal Wear)",
    "USP-S | Kill Confirmed (Minimal Wear)",
    "★ Butterfly Knife | Crimson Web (Field-Tested)",
    "★ Karambit | Doppler (Factory New)",
    "M4A4 | Howl (Factory New)",
    "AWP | Dragon Lore (Field-Tested)",
    "Glock-18 | Water Elemental (Minimal Wear)"
]

@bot.message_handler(commands=['popular'])
def popular_skins(message):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(skin, callback_data=f"add_{skin}") for skin in POPULAR_SKINS]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🔥 Популярные скины. Нажми, чтобы добавить:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_from_popular(call):
    skin_name = call.data[4:]
    bot.answer_callback_query(call.id, f"Добавляю {skin_name}...")
    sell, buy = get_steam_price(skin_name)
    if sell is None or buy is None:
        bot.send_message(call.message.chat.id, f"❌ Не удалось найти скин {skin_name}")
        return
    items = load_items()
    for item in items:
        if item.get("type") == "skin" and item.get("user_id") == call.from_user.id and item.get("item_name") == skin_name:
            bot.send_message(call.message.chat.id, "⚠️ Уже есть в списке")
            return
    items.append({
        "type": "skin",
        "user_id": call.from_user.id,
        "item_name": skin_name,
        "last_notified": None,
        "last_sell": sell,
        "last_buy": buy
    })
    save_items(items)
    bot.send_message(call.message.chat.id, f"✅ Скин {skin_name} добавлен!")

# ------------------ /list ------------------
@bot.message_handler(commands=['list'])
def list_cmd(message):
    items = load_items()
    user_skins = [item for item in items if item.get("type") == "skin" and item.get("user_id") == message.from_user.id]
    if not user_skins:
        bot.send_message(message.chat.id, "📭 Список пуст")
        return
    lines = ["📋 <b>Твои скины:</b>"]
    for i, s in enumerate(user_skins, 1):
        lines.append(f"{i}. {s['item_name']}")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML")

# ------------------ /remove ------------------
@bot.message_handler(commands=['remove'])
def remove_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Укажи номер скина из списка")
        return
    try:
        idx = int(parts[1].strip()) - 1
    except ValueError:
        bot.send_message(message.chat.id, "❌ Нужно указать число")
        return
    items = load_items()
    user_skins = [item for item in items if item.get("type") == "skin" and item.get("user_id") == message.from_user.id]
    if idx < 0 or idx >= len(user_skins):
        bot.send_message(message.chat.id, "❌ Неверный номер")
        return
    to_remove = user_skins[idx]
    items.remove(to_remove)
    save_items(items)
    bot.send_message(message.chat.id, f"✅ Скин {to_remove['item_name']} удалён")

# ------------------ /check ------------------
@bot.message_handler(commands=['check'])
def check_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Напиши название после /check")
        return
    name = parts[1].strip()
    bot.send_message(message.chat.id, f"🔍 Ищу цены для: {name}...")
    sell, buy = get_steam_price(name)
    if sell is None or buy is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить цены")
        return
    profit = buy * (1 - STEAM_COMMISSION) - sell
    status = "🟢 ВЫГОДНО" if profit > 0 else "🔴 НЕ ВЫГОДНО"
    msg = f"{status}\n📦 {name}\n🔻 Продажа: ${sell:.2f}\n🔺 Покупка: ${buy:.2f}\n💰 Прибыль: ${profit:.2f}"
    bot.send_message(message.chat.id, msg)

# ------------------ /calc ------------------
@bot.message_handler(commands=['calc'])
def calc_command(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Пример: /calc AK-47 Redline 5")
        return
    text = parts[1].strip()
    match = re.search(r'(\d+)\s*$', text)
    if not match:
        bot.send_message(message.chat.id, "❌ Не нашёл число. Пример: /calc AK-47 Redline 5")
        return
    quantity = int(match.group(1))
    skin_name = text[:match.start()].strip()
    bot.send_message(message.chat.id, f"🔍 Считаю для {skin_name} x{quantity}...")
    sell, buy = get_steam_price(skin_name)
    if sell is None or buy is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить цены")
        return
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit_per_item = net_buy - sell
    total = profit_per_item * quantity
    msg = (f"📦 {skin_name} x{quantity}\n"
           f"🔻 Продажа: ${sell:.2f}\n"
           f"🔺 Покупка: ${buy:.2f}\n"
           f"💰 Прибыль с одного: ${profit_per_item:.2f}\n"
           f"💵 <b>Общая прибыль: ${total:.2f}</b>")
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

# ---------- ОБЩИЙ ОБРАБОТЧИК ТЕКСТА (для кнопок) ----------
# Он обрабатывает только сообщения, НЕ начинающиеся с '/'
@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_buttons(message):
    text = message.text
    if text == "🔥 Популярные":
        popular_skins(message)
    elif text == "📋 Мои скины":
        list_cmd(message)
    elif text == "🔗 Рефералка":
        referral_command(message)
    elif text == "🔍 Проверить скин":
        bot.send_message(message.chat.id, "Введи название скина для проверки:")
        bot.register_next_step_handler(message, process_check)
    elif text == "➕ Добавить скин":
        bot.send_message(message.chat.id, "Введи название скина для добавления:")
        bot.register_next_step_handler(message, process_add)
    elif text == "🧮 Калькулятор":
        bot.send_message(message.chat.id, "Введи название скина и количество (например: AK-47 Redline 5):")
        bot.register_next_step_handler(message, process_calc)
    else:
        bot.send_message(message.chat.id, "Используй кнопки меню.")

# ---------- Обработчики шагов (после кнопок) ----------
def process_check(message):
    name = message.text.strip()
    bot.send_message(message.chat.id, f"🔍 Ищу цены для: {name}...")
    sell, buy = get_steam_price(name)
    if sell is None or buy is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить цены.")
        return
    profit = buy * (1 - STEAM_COMMISSION) - sell
    status = "🟢 ВЫГОДНО" if profit > 0 else "🔴 НЕ ВЫГОДНО"
    msg = f"{status}\n📦 {name}\n🔻 Продажа: ${sell:.2f}\n🔺 Покупка: ${buy:.2f}\n💰 Прибыль: ${profit:.2f}"
    bot.send_message(message.chat.id, msg)

def process_add(message):
    name = message.text.strip()
    bot.send_message(message.chat.id, f"🔍 Проверяю {name}...")
    sell, buy = get_steam_price(name)
    if sell is None or buy is None:
        bot.send_message(message.chat.id, "❌ Не удалось найти такой скин.")
        return
    items = load_items()
    for item in items:
        if item.get("type") == "skin" and item.get("user_id") == message.from_user.id and item.get("item_name") == name:
            bot.send_message(message.chat.id, "⚠️ Уже есть в списке.")
            return
    items.append({
        "type": "skin",
        "user_id": message.from_user.id,
        "item_name": name,
        "last_notified": None,
        "last_sell": sell,
        "last_buy": buy
    })
    save_items(items)
    bot.send_message(message.chat.id, f"✅ Скин {name} добавлен!")

def process_calc(message):
    text = message.text.strip()
    match = re.search(r'(\d+)\s*$', text)
    if not match:
        bot.send_message(message.chat.id, "❌ Не нашёл число. Пример: AK-47 Redline 5")
        return
    quantity = int(match.group(1))
    skin_name = text[:match.start()].strip()
    if not skin_name:
        bot.send_message(message.chat.id, "❌ Введи название скина перед числом")
        return
    bot.send_message(message.chat.id, f"🔍 Считаю для {skin_name} x{quantity}...")
    sell, buy = get_steam_price(skin_name)
    if sell is None or buy is None:
        bot.send_message(message.chat.id, "❌ Не удалось получить цены.")
        return
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit_per_item = net_buy - sell
    total = profit_per_item * quantity
    msg = (f"📦 {skin_name} x{quantity}\n"
           f"🔻 Продажа: ${sell:.2f}\n"
           f"🔺 Покупка: ${buy:.2f}\n"
           f"💰 Прибыль с одного: ${profit_per_item:.2f}\n"
           f"💵 <b>Общая прибыль: ${total:.2f}</b>")
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

# ---------- Фоновый мониторинг ----------
def monitor():
    while True:
        try:
            items = load_items()
            now = datetime.now().isoformat()
            for entry in items:
                if entry.get("type") != "skin":
                    continue
                user_id = entry.get("user_id")
                name = entry["item_name"]
                last_notified = entry.get("last_notified")
                last_sell = entry.get("last_sell")
                last_buy = entry.get("last_buy")
                print(f"🔄 Проверяю {name}...")
                sell, buy = get_steam_price(name)
                if sell is None or buy is None:
                    time.sleep(2)
                    continue
                profit = buy * (1 - STEAM_COMMISSION) - sell
                if profit > 0:
                    if last_notified:
                        last_time = datetime.fromisoformat(last_notified)
                        hours_passed = (datetime.now() - last_time).total_seconds() / 3600
                        if hours_passed < 6:
                            pass
                        else:
                            msg = f"💰 <b>ВЫГОДНО!</b> {name}\nПродажа: ${sell:.2f}, Покупка: ${buy:.2f}, Прибыль: ${profit:.2f}"
                            bot.send_message(user_id, msg, parse_mode="HTML")
                            entry["last_notified"] = now
                    else:
                        msg = f"💰 <b>ВЫГОДНО!</b> {name}\nПродажа: ${sell:.2f}, Покупка: ${buy:.2f}, Прибыль: ${profit:.2f}"
                        bot.send_message(user_id, msg, parse_mode="HTML")
                        entry["last_notified"] = now
                if last_sell is not None and last_buy is not None:
                    sell_change = abs((sell - last_sell) / last_sell) * 100 if last_sell else 0
                    buy_change = abs((buy - last_buy) / last_buy) * 100 if last_buy else 0
                    if sell_change >= 5 or buy_change >= 5:
                        msg = f"🔔 <b>Изменение цены</b> для {name}\nБыло: {last_sell:.2f}$ / {last_buy:.2f}$, Стало: {sell:.2f}$ / {buy:.2f}$"
                        bot.send_message(user_id, msg, parse_mode="HTML")
                entry["last_sell"] = sell
                entry["last_buy"] = buy
                time.sleep(2)
            save_items(items)
        except Exception as e:
            print(f"⚠️ Ошибка мониторинга: {e}")
        time.sleep(CHECK_INTERVAL)

threading.Thread(target=monitor, daemon=True).start()

# ---------- Запуск ----------
if __name__ == "__main__":
    print("✅ Бот с меню, рефералкой и калькулятором запущен!")
    bot.infinity_polling()

