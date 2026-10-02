import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from bs4 import BeautifulSoup
import aiohttp
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")



# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬТЕ_СЮДА_ТОКЕН_БОТА")
# Товар, за которым следим (ссылка из вашего запроса)
PRODUCT_URL = "https://market.yandex.ru/card/maslo-motornoye-lukoil-genesis-armortech-jp-0w-30-4-l/102207184982"
CHECK_INTERVAL = 600  # Проверять каждые 10 минут (в секундах)
# Порог, при котором отправлять уведомление (в рублях)
TARGET_PRICE = 3000 

# Для доступа к некоторым страницам Яндекса может потребоваться cookie
YA_COOKIE = os.getenv("YA_COOKIE", "") 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Храним последнюю известную цену
last_price = None

async def get_price(url: str) -> float | None:
    """Парсит цену товара по ссылке."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    if YA_COOKIE:
        headers["Cookie"] = YA_COOKIE

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()
                
        soup = BeautifulSoup(html, "html.parser")
        
        # --- ВАЖНО: Селекторы могут меняться. Их нужно проверить вручную. ---
        # Ищем элемент с ценой. Обычно это data-атрибут или специальный класс.
        price_element = soup.find("span", {"data-auto": "price-value"}) or \
                        soup.find("span", class_=lambda x: x and "price" in x.lower())
        
        if price_element:
            price_text = price_element.get_text(strip=True)
            # Очищаем строку от пробелов и знака рубля
            price_clean = "".join(filter(str.isdigit, price_text))
            if price_clean:
                return float(price_clean)
    except Exception as e:
        logging.error(f"Ошибка при парсинге: {e}")
    return None

async def monitor_prices():
    """Фоновая задача для периодической проверки цены."""
    global last_price
    await asyncio.sleep(10) # Небольшая задержка перед первым запуском
    
    while True:
        current_price = await get_price(PRODUCT_URL)
        if current_price:
            logging.info(f"Текущая цена: {current_price} руб.")
            
            # Если цена снизилась или достигла целевой
            if last_price is not None and current_price < last_price:
                # Отправляем уведомление (нужно знать chat_id пользователя)
                # В реальном боте chat_id берется из базы данных при команде /start
                # Здесь для примера используется ваш личный chat_id, который нужно узнать
                # (например, через @userinfobot)
                ADMIN_CHAT_ID = 123456789  # ЗАМЕНИТЕ НА ВАШ ID
                try:
                    await bot.send_message(
                        ADMIN_CHAT_ID, 
                        f"📉 Цена снизилась!\n{PRODUCT_URL}\nБыло: {last_price} руб.\nСтало: {current_price} руб."
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение: {e}")
            
            last_price = current_price
        
        await asyncio.sleep(CHECK_INTERVAL)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет! Я слежу за ценой на товар.\n"
        f"Текущая цена: {last_price} руб.\n"
        f"Порог уведомления: {TARGET_PRICE} руб."
    )

async def main():
    # Запускаем веб-сервер для keep-alive
    await start_web_server()
    # Запускаем фоновый мониторинг
    asyncio.create_task(monitor_prices())
    # Запускаем бота
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main())
