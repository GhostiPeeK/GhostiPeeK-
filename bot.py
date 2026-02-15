import telebot
import requests
import json
import threading
import time
from datetime import datetime
import re
import urllib.parse

# ===== НАСТРОЙКИ =====
TOKEN = "8394148154:AAE_5bdZYtdFsQTIfxGE5EydI0O9OLU5vJU"          # Твой токен от @BotFather
STEAM_COMMISSION = 0.13        # Комиссия Steam 13%
CHECK_INTERVAL = 600            # Проверка каждые 10 минут
PRICE_CHANGE_THRESHOLD = 5.0    # Порог изменения цены для уведомления (%)
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
    """
    Получает цены через официальный Steam API
    Возвращает (sell_price, buy_price) или (None, None)
    """
    print(f"📡 Запрашиваю Steam API для: {item_name}")
    
    encoded_name = urllib.parse.quote(item_name)
    url = f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={encoded_name}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"❌ Ошибка Steam API: статус {response.status_code}")
            return None, None
        
        data = response.json()
        if not data.get("success"):
            print(f"❌ Steam API вернул ошибку: {data}")
            return None, None
        
        lowest_price = data.get("lowest_price")
        if not lowest_price:
            print("❌ Нет цены продажи")
            return None, None
        
        sell_match = re.search(r'\$([0-9,\.]+)', lowest_price)
        sell_price = float(sell_match.group(1).replace(',', '')) if sell_match else None
        
        median_price = data.get("median_price")
        buy_price = None
        if median_price:
            buy_match = re.search(r'\$([0-9,\.]+)', median_price)
            buy_price = float(buy_match.group(1).replace(',', '')) if buy_match else None
        else:
            buy_price = sell_price * 0.85 if sell_price else None
        
        if sell_price and buy_price:
            print(f"💰 Найдено: продажа {sell_price}$, покупка {buy_price}$")
            return sell_price, buy_price
        else:
            print("❌ Не удалось распарсить цены")
            return None, None
            
    except Exception as e:
        print(f"⚠️ Ошибка при запросе Steam API: {e}")
        return None, None

# ---------- Проверка предмета ----------
def check_item(item_name):
    sell, buy = get_steam_price(item_name)
    if sell is None or buy is None:
        return {"success": False, "error": "Нет цен"}
    
    net_buy = buy * (1 - STEAM_COMMISSION)
    profit = net_buy - sell
    
    return {
        "success": True,
        "sell": sell,
        "buy": buy,
        "profit": profit,
        "name": item_name
    }

# ---------- Фоновый мониторинг ----------
def monitor():
    while True:
        try:
            items = load_items()
            now = datetime.now().isoformat()
            
            for entry in items:
                chat_id = entry["chat_id"]
                name = entry["item_name"]
                last_notified_profit = entry.get("last_notified")  # для выгодной покупки
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
                
                # --- 1. Уведомление о выгодной покупке (прибыль > 0) ---
                if profit > 0:
                    # Проверяем, не отправляли ли за последние 6 часов
                    if last_notified_profit:
                        last_time = datetime.fromisoformat(last_notified_profit)
                        hours_passed = (datetime.now() - last_time).total_seconds() / 3600
                        if hours_passed < 6:
                            print(f"⏰ Недавно уведомляли о выгоде, пропускаем")
                        else:
                            msg = (
                                f"💰 **ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ!**\n"
                                f"Предмет: {name}\n"
                                f"🔻 Продажа: {sell:.2f}$\n"
                                f"🔺 Покупка: {buy:.2f}$\n"
                                f"💵 Прибыль (после комиссии): {profit:.2f}$"
                            )
                            try:
                                bot.send_message(chat_id, msg, parse_mode="Markdown")
                                entry["last_notified"] = now
                                print(f"✅ Уведомление о выгоде отправлено")
                            except Exception as e:
                                print(f"❌ Ошибка отправки: {e}")
                    else:
                        # Первое уведомление о выгоде
                        msg = (
                            f"💰 **ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ!**\n"
                            f"Предмет: {name}\n"
                            f"🔻 Продажа: {sell:.2f}$\n"
                            f"🔺 Покупка: {buy:.2f}$\n"
                            f"💵 Прибыль (после комиссии): {profit:.2f}$"
                        )
                        try:
                            bot.send_message(chat_id, msg, parse_mode="Markdown")
                            entry["last_notified"] = now
                            print(f"✅ Уведомление о выгоде отправлено")
                        except Exception as e:
                            print(f"❌ Ошибка отправки: {e}")
                
                # --- 2. Уведомление об изменении цены (порог 5%) ---
                if last_sell is not None and last_buy is not None:
                    # Изменение цены продажи
                    sell_change = ((sell - last_sell) / last_sell) * 100
                    # Изменение цены покупки
                    buy_change = ((buy - last_buy) / last_buy) * 100
                    
                    changes = []
                    if abs(sell_change) >= PRICE_CHANGE_THRESHOLD:
                        direction = "📈 выросла" if sell_change > 0 else "📉 упала"
                        changes.append(f"Цена продажи {direction} на {abs(sell_change):.1f}% (была {last_sell:.2f}$, стала {sell:.2f}$)")
                    if abs(buy_change) >= PRICE_CHANGE_THRESHOLD:
                        direction = "📈 выросла" if buy_change > 0 else "📉 упала"
                        changes.append(f"Цена покупки {direction} на {abs(buy_change):.1f}% (была {last_buy:.2f}$, стала {buy:.2f}$)")
                    
                    if changes:
                        msg = f"🔔 **Изменение цены** для {name}:\n" + "\n".join(changes)
                        try:
                            bot.send_message(chat_id, msg, parse_mode="Markdown")
                            print(f"✅ Уведомление об изменении цены отправлено")
                        except Exception as e:
                            print(f"❌ Ошибка отправки уведомления об изменении: {e}")
                
                # Обновляем сохранённые цены
                entry["last_sell"] = sell
                entry["last_buy"] = buy
                
                time.sleep(2)  # Пауза между проверками
            
            save_items(items)
            
        except Exception as e:
            print(f"⚠️ Ошибка в monitor: {e}")
        
        time.sleep(CHECK_INTERVAL)

# Запуск фонового потока
threading.Thread(target=monitor, daemon=True).start()

# ---------- Команды бота ----------
@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.reply_to(message,
        "🤖 **CS2 Трейдинг Бот**\n\n"
        "Я отслеживаю цены на скины и присылаю уведомления:\n"
        f"• Когда цена меняется на {PRICE_CHANGE_THRESHOLD}% и более\n"
        "• Когда появляется выгодная покупка (прибыль >0)\n\n"
        "**Команды:**\n"
        "/add <название> — добавить скин в список отслеживания\n"
        "/list — показать все отслеживаемые скины\n"
        "/remove <номер> — удалить скин из списка\n"
        "/check <название> — разовая проверка (без добавления)\n\n"
        "**Пример:** /add AK-47 | Redline (Field-Tested)\n\n"
        "⚠️ **Важно:** Используйте точные английские названия, как в Steam Market."
    , parse_mode="Markdown")

@bot.message_handler(commands=['check'])
def check_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Напиши название после /check\nПример: /check AK-47 | Redline (Field-Tested)")
        return
    
    name = parts[1].strip()
    bot.reply_to(message, f"🔍 Ищу цены для: {name}...")
    
    res = check_item(name)
    if not res["success"]:
        bot.reply_to(message, f"❌ {res.get('error', 'Не удалось получить цены')}. Попробуй уточнить название.")
        return
    
    status = "🟢 **ВЫГОДНО**" if res["profit"] > 0 else "🔴 **НЕ ВЫГОДНО**"
    msg = (
        f"{status}\n"
        f"📦 {name}\n"
        f"🔻 Продажа: {res['sell']:.2f}$\n"
        f"🔺 Покупка: {res['buy']:.2f}$\n"
        f"💰 Чистая прибыль (после комиссии 13%): {res['profit']:.2f}$"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Укажи название скина после /add")
        return
    
    name = parts[1].strip()
    
    bot.reply_to(message, f"🔍 Проверяю существование скина: {name}...")
    res = check_item(name)
    if not res["success"]:
        bot.reply_to(message, "❌ Не удалось найти такой скин. Проверь название и попробуй ещё раз.")
        return
    
    items = load_items()
    for item in items:
        if item["chat_id"] == message.chat.id and item["item_name"].lower() == name.lower():
            bot.reply_to(message, "⚠️ Этот скин уже есть в твоём списке.")
            return
    
    # Добавляем с сохранением текущих цен
    items.append({
        "chat_id": message.chat.id,
        "item_name": name,
        "last_notified": None,
        "last_sell": res["sell"],
        "last_buy": res["buy"]
    })
    save_items(items)
    
    bot.reply_to(message, 
        f"✅ **Скин добавлен в список отслеживания!**\n"
        f"📦 {name}\n"
        f"⏱️ Буду проверять каждые {CHECK_INTERVAL//60} минут.\n\n"
        f"Текущая цена продажи: {res['sell']:.2f}$, покупки: {res['buy']:.2f}$\n"
        f"При изменении цены на {PRICE_CHANGE_THRESHOLD}% пришлю уведомление."
    , parse_mode="Markdown")

@bot.message_handler(commands=['list'])
def list_cmd(message):
    items = load_items()
    user_items = [item for item in items if item["chat_id"] == message.chat.id]
    
    if not user_items:
        bot.reply_to(message, "📭 Твой список отслеживания пуст. Добавь скины через /add")
        return
    
    lines = ["📋 **Твои скины:**"]
    for i, item in enumerate(user_items, 1):
        lines.append(f"{i}. {item['item_name']}")
    
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=['remove'])
def remove_cmd(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Укажи номер скина из списка (команда /list)")
        return
    
    items = load_items()
    user_items = [item for item in items if item["chat_id"] == message.chat.id]
    
    try:
        idx = int(parts[1].strip()) - 1
        if 0 <= idx < len(user_items):
            item_to_remove = user_items[idx]
            items.remove(item_to_remove)
            save_items(items)
            bot.reply_to(message, f"✅ Скин **{item_to_remove['item_name']}** удалён из списка.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Неверный номер. Используй /list чтобы увидеть список.")
    except ValueError:
        bot.reply_to(message, "❌ Нужно указать номер (например: /remove 3)")

# ---------- Запуск ----------
if __name__ == "__main__":
    print("✅ Бот с уведомлениями об изменении цен запущен!")
    print(f"⏱️ Интервал проверки: {CHECK_INTERVAL//60} минут")
    print(f"📊 Порог изменения цены: {PRICE_CHANGE_THRESHOLD}%")
    bot.infinity_polling()