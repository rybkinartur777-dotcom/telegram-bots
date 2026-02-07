# 💻 Примеры кода для расширения бота

Используйте эти примеры как шаблон для добавления новых функций в `bot.py`

## 1️⃣ Простой текстовый ответ

```python
@dp.message()
async def echo_handler(message: Message):
    """Повторяет все сообщения пользователя"""
    if message.text:
        await message.reply(f"Вы сказали: {message.text}")
        return
```

## 2️⃣ Команда с параметрами

```python
@dp.message(CommandStart())
async def cmd_help(message: Message):
    """Справка по командам"""
    help_text = (
        "/start - Приветствие\n"
        "/help - Эта справка\n"
        "/stats - Статистика бота"
    )
    await message.answer(help_text)
```

## 3️⃣ Обработка видео

```python
@dp.message()
async def handle_video(message: Message):
    """Обработка видеофайлов"""
    if message.video:
        file_id = message.video.file_id
        file_size = message.video.file_size
        
        await message.reply(
            f"Получено видео!\n"
            f"Размер: {file_size / 1024 / 1024:.1f} МБ"
        )
        return
```

## 4️⃣ Кнопки (Inline Keyboard)

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@dp.message(CommandStart())
async def cmd_buttons(message: Message):
    """Отправляет сообщение с кнопками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Google", url="https://google.com"),
            InlineKeyboardButton(text="Telegram", url="https://telegram.org")
        ],
        [
            InlineKeyboardButton(text="Нажми меня", callback_data="button_pressed")
        ]
    ])
    
    await message.answer("Выберите:", reply_markup=keyboard)

@dp.callback_query()
async def handle_callback(query):
    """Обработка нажатия на кнопку"""
    if query.data == "button_pressed":
        await query.answer("Спасибо за клик!", show_alert=False)
```

## 5️⃣ Клавиатура (Reply Keyboard)

```python
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

@dp.message(CommandStart())
async def cmd_keyboard(message: Message):
    """Отправляет сообщение с клавиатурой"""
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Опция 1"), KeyboardButton(text="Опция 2")],
        [KeyboardButton(text="Опция 3")]
    ], resize_keyboard=True)
    
    await message.answer("Выберите опцию:", reply_markup=keyboard)
```

## 6️⃣ Сохранение в файл

```python
import json

def save_data(user_id, data):
    """Сохраняет данные пользователя"""
    with open(f"users/{user_id}.json", "w") as f:
        json.dump(data, f)

def load_data(user_id):
    """Загружает данные пользователя"""
    try:
        with open(f"users/{user_id}.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

@dp.message()
async def save_message(message: Message):
    """Сохраняет текст пользователя"""
    if message.text:
        data = {
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "text": message.text,
            "timestamp": str(message.date)
        }
        save_data(message.from_user.id, data)
        await message.reply("Сохранено!")
        return
```

## 7️⃣ Задержка/Таймер

```python
import asyncio

@dp.message()
async def delayed_response(message: Message):
    """Ответ с задержкой в 5 секунд"""
    if message.text == "жди":
        status = await message.reply("⏳ Обработка...")
        await asyncio.sleep(5)  # Ждём 5 секунд
        await status.edit_text("✅ Готово!")
        return
```

## 8️⃣ Обработка ошибок

```python
@dp.message()
async def safe_handler(message: Message):
    """Обработка с проверкой ошибок"""
    try:
        # Ваш код
        result = 10 / 0  # Ошибка!
        await message.answer(f"Результат: {result}")
    except ZeroDivisionError:
        await message.reply("Ошибка: деление на ноль!")
    except Exception as e:
        await message.reply(f"Неизвестная ошибка: {str(e)}")
```

## 9️⃣ Проверка прав доступа

```python
ADMIN_IDS = [123456789, 987654321]  # ID администраторов

@dp.message()
async def admin_only(message: Message):
    """Команда только для администраторов"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен!")
        return
    
    await message.reply("✅ Привет, администратор!")
    return
```

## 🔟 Отправка файла

```python
from aiogram.types import FSInputFile

@dp.message(CommandStart())
async def send_file(message: Message):
    """Отправляет файл"""
    file = FSInputFile("path/to/file.txt")
    await message.answer_document(document=file)
```

## 1️⃣1️⃣ Массовая отправка сообщений

```python
USER_IDS = [123456789, 987654321]  # IDs получателей

async def broadcast_message(text: str):
    """Отправляет сообщение всем"""
    for user_id in USER_IDS:
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            print(f"Ошибка для {user_id}: {e}")
```

## 1️⃣2️⃣ Взаимодействие с несколькими обработчиками

```python
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    name = State()
    age = State()

@dp.message(CommandStart())
async def start_form(message: Message, state: FSMContext):
    """Начало формы"""
    await state.set_state(Form.name)
    await message.answer("Как вас зовут?")

@dp.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    await state.update_data(name=message.text)
    await state.set_state(Form.age)
    await message.answer("Сколько вам лет?")

@dp.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    data = await state.get_data()
    await message.answer(
        f"Спасибо! Вас зовут {data['name']} и вам {message.text} лет"
    )
    await state.clear()
```

## 💾 Практический пример: Счетчик сообщений

```python
message_count = {}

@dp.message()
async def count_messages(message: Message):
    """Считает сообщения от каждого пользователя"""
    user_id = message.from_user.id
    
    # Увеличиваем счетчик
    if user_id not in message_count:
        message_count[user_id] = 0
    message_count[user_id] += 1
    
    # Сообщаем статистику каждое 10-е сообщение
    if message_count[user_id] % 10 == 0:
        await message.reply(
            f"Вы отправили {message_count[user_id]} сообщений!"
        )
    return
```

---

## 📚 Полезные ссылки

- [aiogram документация](https://docs.aiogram.dev/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

Успехов в разработке! 🚀
