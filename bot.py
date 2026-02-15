import telebot
import requests
import re
import json
import threading
import time
from datetime import datetime
import urllib.parse
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== НАСТРОЙКИ =====
TOKEN = "8394148154:AAE_5bdZYtdFsQTIfxGE5EydI0O9OLU5vJU"  # Твой токен
STEAM_COMMISSION = 0.13        # Комиссия Steam 13%
CHECK_INTERVAL = 600            # Проверка каждые 10 минут
ITEMS_FILE = "items.json"       # Файл для хранения списка скинов
# =====================

bot = telebot.TeleBot(TOKEN)

# ---------- Работа с файлом ----------
def load_items():
    try:
        with open(ITEMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_items(items):
    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ---------- Получение цен через Steam API ----------
def get_steam_price(item_name):
    print(f"📡 Запрашиваю Steam API для: {item_name}")
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
        sell = float(sell_match.group(1).replace(',', '')) if sell_match else None
        median = data.get("median_price")
        buy = None
        if median:
            buy_match = re.search(r'\$([0-9,\.]+)', median)
            buy = float(buy_match.group(1).replace(',', '')) if buy_match else None
        else:
            buy = sell * 0.85 if sell else None
        return sell, buy
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        return None, None

def check_item(item_name):
    sell, buy = get_steam_price(item_name)
    if sell is None or buy is None:
        return {"success": False, "error": "Нет цен"}
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit = net_buy - sell
    return {"success": True, "sell": sell, "buy": buy, "profit": profit, "name": item_name}

# ---------- Список популярных скинов ----------
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
    buttons = []
    for skin in POPULAR_SKINS:
        buttons.append(InlineKeyboardButton(skin, callback_data=f"add_{skin}"))
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🔥 Популярные скины. Нажми, чтобы добавить в отслеживание:", reply_markup=markup)

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
        if item.get("chat_id") == call.message.chat.id and item.get("item_name") == skin_name:
            bot.send_message(call.message.chat.id, "⚠️ Уже есть в списке")
            return
    
    items.append({
        "chat_id": call.message.chat.id,
        "item_name": skin_name,
        "last_notified": None,
        "last_sell": sell,
        "last_buy": buy
    })
    save_items(items)
    bot.send_message(call.message.chat.id, f"✅ Скин {skin_name} добавлен!")

# ---------- Реферальная система ----------
def get_referral_link(user_id, bot_username):
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

@bot.message_handler(commands=['referral'])
def referral_command(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    link = get_referral_link(user_id, bot_username)
    
    # Подсчёт приглашённых
    items = load_items()
    referrals = 0
    for item in items:
        if item.get("referred_by") == user_id:
            referrals += 1
    
    bot.reply_to(message,
        f"🔗 **Твоя реферальная ссылка:**\n{link}\n\n"
        f"📊 Приглашено друзей: {referrals}\n"
        f"За каждого друга ты получаешь +1 в рейтинг (пока просто счётчик)."
    , parse_mode="Markdown")

# ---------- Основные команды ----------
@bot.message_handler(commands=['start', 'help'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Проверка на реферальный переход
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].split("_")[1])
        if referrer_id != user_id:
            items = load_items()
            # Ищем пользователя в базе
            user_found = False
            for item in items:
                if item.get("user_id") == user_id:
                    item["referred_by"] = referrer_id
                    user_found = True
                    break
            if not user_found:
                items.append({
                    "user_id": user_id,
                    "referred_by": referrer_id,
                    "last_notified": None,
                    "last_sell": None,
                    "last_buy": None
                })
            save_items(items)
    
    bot.reply_to(message,
        "🤖 **CS2 Трейдинг Бот**\n\n"
        "/check <название> — разовая проверка\n"
        "/popular — выбрать из популярных скинов\n"
        "/referral — получить реферальную ссылку\n"
        "/list — показать список\n"
        "/remove <номер> — удалить из списка\n"
        "/calc <скин> <количество> — калькулятор прибыли\n\n"
        "Пример: /check AK-47 | Redline (Field-Tested)"
    , parse_mode="Markdown")

@bot.message_handler(commands=['check'])
def check_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Напиши название после /check")
        return
    name = parts[1].strip()
    bot.reply_to(message, f"🔍 Ищу цены для: {name}...")
    res = check_item(name)
    if not res["success"]:
        bot.reply_to(message, f"❌ {res.get('error', 'Ошибка')}")
        return
    status = "🟢 ВЫГОДНО" if res["profit"] > 0 else "🔴 НЕ ВЫГОДНО"
    msg = (
        f"{status}\n"
        f"📦 {name}\n"
        f"🔻 Продажа: {res['sell']:.2f}$\n"
        f"🔺 Покупка: {res['buy']:.2f}$\n"
        f"💰 Прибыль: {res['profit']:.2f}$"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Укажи название после /add")
        return
    name = parts[1].strip()
    bot.reply_to(message, f"🔍 Проверяю {name}...")
    res = check_item(name)
    if not res["success"]:
        bot.reply_to(message, "❌ Не удалось найти такой скин")
        return
    items = load_items()
    for item in items:
        if item.get("chat_id") == message.chat.id and item.get("item_name").lower() == name.lower():
            bot.reply_to(message, "⚠️ Уже есть в списке")
            return
    items.append({
        "chat_id": message.chat.id,
        "item_name": name,
        "last_notified": None,
        "last_sell": res["sell"],
        "last_buy": res["buy"]
    })
    save_items(items)
    bot.reply_to(message, f"✅ Скин добавлен!")

@bot.message_handler(commands=['list'])
def list_cmd(message):
    items = load_items()
    user_items = [item for item in items if item.get("chat_id") == message.chat.id]
    if not user_items:
        bot.reply_to(message, "📭 Список пуст")
        return
    lines = ["📋 **Твои скины:**"]
    for i, item in enumerate(user_items, 1):
        lines.append(f"{i}. {item['item_name']}")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=['remove'])
def remove_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Укажи номер из списка")
        return
    items = load_items()
    user_items = [item for item in items if item.get("chat_id") == message.chat.id]
    try:
        idx = int(parts[1].strip()) - 1
        if 0 <= idx < len(user_items):
            to_remove = user_items[idx]
            items.remove(to_remove)
            save_items(items)
            bot.reply_to(message, "✅ Удалено")
        else:
            bot.reply_to(message, "❌ Неверный номер")
    except ValueError:
        bot.reply_to(message, "❌ Нужно указать номер")

@bot.message_handler(commands=['calc'])
def calc_command(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "❌ Пример: /calc AK-47 | Redline (Field-Tested) 5")
        return
    name = parts[1].strip()
    try:
        quantity = int(parts[2].strip())
    except ValueError:
        bot.reply_to(message, "❌ Количество должно быть числом")
        return
    bot.reply_to(message, f"🔍 Считаю для {name} x{quantity}...")
    sell, buy = get_steam_price(name)
    if sell is None or buy is None:
        bot.reply_to(message, "❌ Не удалось получить цены")
        return
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit_per_item = net_buy - sell
    total_profit = profit_per_item * quantity
    msg = (
        f"📦 {name} x{quantity}\n"
        f"🔻 Цена продажи: ${sell:.2f}\n"
        f"🔺 Цена покупки: ${buy:.2f}\n"
        f"💰 Прибыль с одного: ${profit_per_item:.2f}\n"
        f"💵 **Общая прибыль: ${total_profit:.2f}**"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

# ---------- Фоновый мониторинг ----------
def monitor():
    while True:
        try:
            items = load_items()
            now = datetime.now().isoformat()
            for entry in items:
                if "item_name" not in entry:
                    continue
                chat_id = entry.get("chat_id")
                name = entry["item_name"]
                last_notified = entry.get("last_notified")
                last_sell = entry.get("last_sell")
                last_buy = entry.get("last_buy")
                
                print(f"🔄 Проверяю {name}...")
                res = check_item(name)
                if not res["success"]:
                    time.sleep(2)
                    continue
                sell = res["sell"]
                buy = res["buy"]
                profit = res["profit"]
                
                # Уведомление о выгодной покупке
                if profit > 0 and (not last_notified or (datetime.now() - datetime.fromisoformat(last_notified)).total_seconds() > 21600):
                    msg = f"💰 **ВЫГОДНО!** {name}\n🔻 Продажа: {sell:.2f}$\n🔺 Покупка: {buy:.2f}$\n💵 Прибыль: {profit:.2f}$"
                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                    entry["last_notified"] = now
                
                # Уведомление об изменении цены
                if last_sell and last_buy:
                    sell_change = abs((sell - last_sell) / last_sell) * 100
                    buy_change = abs((buy - last_buy) / last_buy) * 100
                    if sell_change >= 5 or buy_change >= 5:
                        msg = f"🔔 **Изменение цены** для {name}\nБыло: {last_sell:.2f}$ / {last_buy:.2f}$\nСтало: {sell:.2f}$ / {buy:.2f}$"
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
                
                entry["last_sell"] = sell
                entry["last_buy"] = buy
                time.sleep(2)
            save_items(items)
        except Exception as e:
            print(f"⚠️ Ошибка в monitor: {e}")
        time.sleep(CHECK_INTERVAL)

# Запуск фонового потока
threading.Thread(target=monitor, daemon=True).start()

if __name__ == "__main__":
    print("✅ Бот запущен с популярными скинами, рефералкой и калькулятором!")
    bot.infinity_polling()

