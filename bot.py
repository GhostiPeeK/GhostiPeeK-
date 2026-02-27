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
TOKEN = os.environ.get("BOT_TOKEN")  # Токен из переменной окружения
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

def check_item(item_name):
    sell, buy = get_steam_price(item_name)
    if sell is None or buy is None:
        return {"success": False, "error": "Нет цен"}
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit = net_buy - sell
    return {"success": True, "sell": sell, "buy": buy, "profit": profit, "name": item_name}

# ---------- Меню ----------
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🔥 Популярные"),
        KeyboardButton("📋 Мои скины"),
        KeyboardButton("🔗 Рефералка"),
        KeyboardButton("🔍 Проверить скин"),
        KeyboardButton("➕ Добавить скин"),
        KeyboardButton("❓ Помощь")
    )
    return markup

# ---------- Кнопка "Назад" ----------
def back_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🔙 Назад"))
    return markup

# ---------- Обработчик "Назад" ----------
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def go_back(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

# ---------- Команда /start ----------
@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        "Привет! 👋\n\n"
        "Этот бот отслеживает за вас изменения цен на торговой площадке Steam, "
        "некоторые функции могут не работать, бот находится на стадии разработки.\n\n"
        "Если хотите что-то увидеть в боте пишите @GhostiPeeK_2.\n\n"
        "Удачного использования бота! 🎮"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu())

# ---------- Кнопка "❓ Помощь" ----------
@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button(message):
    help_text = (
        "ℹ️ <b>Справка по боту:</b>\n\n"
        "<b>🔥 Популярные</b> — список популярных скинов (можно добавить)\n"
        "<b>📋 Мои скины</b> — список отслеживаемых скинов\n"
        "<b>🔗 Рефералка</b> — получить реферальную ссылку\n"
        "<b>🔍 Проверить скин</b> — разовая проверка цены\n"
        "<b>➕ Добавить скин</b> — добавить скин в отслеживание\n\n"
        "По всем вопросам: @GhostiPeeK_2"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML", reply_markup=main_menu())

# ---------- Кнопка "🔗 Рефералка" ----------
@bot.message_handler(func=lambda message: message.text == "🔗 Рефералка")
def referral_button(message):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    msg_text = f"🔗 <b>Твоя реферальная ссылка:</b>\n{link}"
    bot.send_message(message.chat.id, msg_text, parse_mode="HTML", reply_markup=main_menu())

# ---------- Популярные скины ----------
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
@bot.message_handler(func=lambda message: message.text == "🔥 Популярные")
def popular_skins(message):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(skin, callback_data=f"add_{skin}") for skin in POPULAR_SKINS]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🔥 Популярные скины. Нажми, чтобы добавить:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_from_popular(call):
    skin_name = call.data[4:]
    bot.answer_callback_query(call.id, f"Добавляю {skin_name}...")
    res = check_item(skin_name)
    if not res["success"]:
        bot.send_message(call.message.chat.id, f"❌ Не удалось найти скин {skin_name}")
        return
    
    items = load_items()
    for item in items:
        if item.get("user_id") == call.from_user.id and item.get("item_name") == skin_name:
            bot.send_message(call.message.chat.id, "⚠️ Уже есть в списке")
            return
    
    items.append({
        "user_id": call.from_user.id,
        "item_name": skin_name,
        "last_notified": None,
        "last_sell": res["sell"],
        "last_buy": res["buy"]
    })
    save_items(items)
    bot.send_message(call.message.chat.id, f"✅ Скин {skin_name} добавлен!", reply_markup=main_menu())

# ---------- Мои скины ----------
@bot.message_handler(commands=['list'])
@bot.message_handler(func=lambda message: message.text == "📋 Мои скины")
def list_cmd(message):
    items = load_items()
    user_skins = [item for item in items if item.get("user_id") == message.from_user.id and item.get("item_name")]
    
    if not user_skins:
        bot.send_message(message.chat.id, "📭 Список пуст", reply_markup=main_menu())
        return
    
    lines = ["📋 <b>Твои скины:</b>"]
    for i, s in enumerate(user_skins, 1):
        lines.append(f"{i}. {s['item_name']}")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML", reply_markup=main_menu())

# ---------- Проверить скин ----------
@bot.message_handler(func=lambda message: message.text == "🔍 Проверить скин")
def check_prompt(message):
    msg = bot.send_message(message.chat.id, "Введи название скина для проверки:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, process_check)

def process_check(message):
    if message.text == "🔙 Назад":
        go_back(message)
        return
    
    name = message.text.strip()
    bot.send_message(message.chat.id, f"🔍 Ищу цены для: {name}...")
    res = check_item(name)
    
    if not res["success"]:
        bot.send_message(message.chat.id, f"❌ {res.get('error', 'Ошибка')}", reply_markup=main_menu())
        return
    
    status = "🟢 ВЫГОДНО" if res["profit"] > 0 else "🔴 НЕ ВЫГОДНО"
    msg_text = f"{status}\n📦 {name}\n🔻 Продажа: ${res['sell']:.2f}\n🔺 Покупка: ${res['buy']:.2f}\n💰 Прибыль: ${res['profit']:.2f}"
    bot.send_message(message.chat.id, msg_text, reply_markup=main_menu())

# ---------- Добавить скин ----------
@bot.message_handler(func=lambda message: message.text == "➕ Добавить скин")
def add_prompt(message):
    msg = bot.send_message(message.chat.id, "Введи название скина для добавления:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, process_add)

def process_add(message):
    if message.text == "🔙 Назад":
        go_back(message)
        return
    
    name = message.text.strip()
    bot.send_message(message.chat.id, f"🔍 Проверяю {name}...")
    res = check_item(name)
    
    if not res["success"]:
        bot.send_message(message.chat.id, "❌ Не удалось найти такой скин.", reply_markup=main_menu())
        return
    
    items = load_items()
    for item in items:
        if item.get("user_id") == message.from_user.id and item.get("item_name") == name:
            bot.send_message(message.chat.id, "⚠️ Уже есть в списке", reply_markup=main_menu())
            return
    
    items.append({
        "user_id": message.from_user.id,
        "item_name": name,
        "last_notified": None,
        "last_sell": res["sell"],
        "last_buy": res["buy"]
    })
    save_items(items)
    bot.send_message(message.chat.id, f"✅ Скин {name} добавлен в список!", reply_markup=main_menu())

# ---------- Команда /remove ----------
@bot.message_handler(commands=['remove'])
def remove_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Укажи номер скина из списка", reply_markup=main_menu())
        return
    
    try:
        idx = int(parts[1].strip()) - 1
    except ValueError:
        bot.send_message(message.chat.id, "❌ Нужно указать число", reply_markup=main_menu())
        return
    
    items = load_items()
    user_skins = [item for item in items if item.get("user_id") == message.from_user.id and item.get("item_name")]
    
    if idx < 0 or idx >= len(user_skins):
        bot.send_message(message.chat.id, "❌ Неверный номер", reply_markup=main_menu())
        return
    
    to_remove = user_skins[idx]
    items.remove(to_remove)
    save_items(items)
    bot.send_message(message.chat.id, f"✅ Скин {to_remove['item_name']} удалён", reply_markup=main_menu())

# ---------- Фоновый мониторинг ----------
def monitor():
    while True:
        try:
            items = load_items()
            now = datetime.now().isoformat()
            for entry in items:
                if not entry.get("item_name"):
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
                
                # Уведомление о выгодной покупке
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
                
                # Уведомление об изменении цены (порог 5%)
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
    print("✅ Бот запущен!")
    bot.infinity_polling()