import os
from uuid import uuid4
import jdatetime
import requests
from bs4 import BeautifulSoup
import psycopg2
from threading import Event, Thread
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    InlineQueryHandler,
    MessageHandler,
    Updater,
)


DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.environ.get("PORT", "5000"))
TOKEN = "YOUR OWN TOKEN"
titles = []
prices = []
percents = []
costs = []
status = []


def update_db():
    this_changes = []
    this_live_prices = []
    this_titles = []

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")

    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS main (
            title TEXT,
            price TEXT,
            percent TEXT,
            cost TEXT,
            status TEXT);"""
    )
    cursor.execute("DELETE FROM main")
    """scrape data"""
    r = requests.get("https://www.tgju.org/currency")
    soup = BeautifulSoup(r.content, "html.parser")
    [this_live_prices.append(p.text) for p in soup.select("th+ .nf")]
    [this_titles.append(p.text) for p in soup.select(".pointer th")]
    for i in range(len(this_live_prices)):
        this_live_prices[i] = (this_live_prices[i]).replace(",", "")
        this_live_prices[i] = this_live_prices[i][:-1]
        this_live_prices[i] = "{:,}".format(int(this_live_prices[i]))

    for p in soup.select(".nf span"):
        if p.attrs["class"] != []:
            this_changes.append(p.text.split() + p.attrs["class"])
        else:
            this_changes.append(p.text.split() + ["None"])

    for i in range(len(this_changes)):
        this_changes[i][1] = (this_changes[i][1]).replace(",", "")
        this_changes[i][1] = this_changes[i][1][:-1]
        if this_changes[i][1] != "":
            this_changes[i][1] = "{:,}".format(int(this_changes[i][1]))
        else:
            this_changes[i][1] = "None"

    for x in range(len(this_titles)):

        title = this_titles[x]
        price = this_live_prices[x]
        percent = this_changes[x][0]
        cost = this_changes[x][1]

        status = this_changes[x][2]
        cursor.execute(
            " INSERT INTO main VALUES(%s,%s.%s,%s,%s)",
            (title, price, percent , cost, status)
        )
    conn.commit()
    conn.close()


def read_db():
    titles.clear()
    prices.clear()
    percents.clear()
    costs.clear()

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")

    cursor = conn.cursor()
    cursor.execute("select * from main;")
    data = cursor.fetchall()
    for item in data:
        titles.append(item[0])
        prices.append(item[1])
        percents.append(item[2])
        costs.append(item[3])
        status.append(item[4])


main_keyboard = [
    [
        InlineKeyboardButton("راهنما", callback_data="101"),
        InlineKeyboardButton("ارز ها", callback_data="100"),
    ]
]

titles_keyboard = []


def create_keyboard_button():
    """call this function after update_data()"""
    ax = 0
    bx = 1
    cx = 2  # index
    chunk = 3
    for x in range(0, len(titles), chunk):
        for a, b, c in [titles[x : x + chunk]]:
            titles_keyboard.append(
                [
                    InlineKeyboardButton(a, callback_data=str(ax)),
                    InlineKeyboardButton(b, callback_data=str(bx)),
                    InlineKeyboardButton(c, callback_data=str(cx)),
                ]
            )
            ax += chunk
            bx += chunk
            cx += chunk


def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    text = f"""{user.first_name} سلام
🤖 به ربات هورچی خوش امدی 🤖
 قیمت به زنده ارز هارو از من بپرس ☺

"""
    update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(main_keyboard)
    )


def give_result_text(title, price, percent, cost, status):
    result_text = """قیمت {} به تومان
قیمت زنده:‌ {}
{} تومان {} نسبت به دیروز 
{}{}
تاریخ: {}
"""
    """get args, edit a resutl text, and return it"""
    date = jdatetime.datetime.now().strftime("%m/%d")
    if status == "high":
        text = result_text.format(title, price, cost, "افزایش", "+", percent, date)
        return text
    elif status == "low":
        text = result_text.format(title, price, cost, "کاهش", "-", percent, date)
        return text
    else:
        this_result = (
            "قیمت {} به تومان\nقیمت زنده: {}\nبدون تغییر قیمت، نسبت به دیروز\nتاریخ: {}"
        )
        text = this_result.format(title, price, date)
        return text


def inlinequery(update: Update, context: CallbackContext):
    read_db()
    results = []
    for i in range(len(titles)):
        inline = InlineQueryResultArticle(
            id=str(uuid4()),
            title=titles[i],
            input_message_content=InputTextMessageContent(
                give_result_text(
                    titles[i], prices[i], percents[i], costs[i], status[i]
                ),
            ),
        )
        results.append(inline)
    update.inline_query.answer(results)


def button(update: Update, context: CallbackQueryHandler):
    query = update.callback_query
    choice = int(query["data"])

    if choice == 100:
        read_db()
        titles_keyboard.clear()
        create_keyboard_button()
        query.edit_message_text(
            text="🔰انتخاب کنید🔰", reply_markup=InlineKeyboardMarkup(titles_keyboard)
        )

    if choice <= 35:
        text = give_result_text(
            titles[choice],
            prices[choice],
            percents[choice],
            costs[choice],
            status[choice],
        )
        query.edit_message_text(text)

        keyboard = [
            [
                InlineKeyboardButton("راهنما", callback_data="101"),
                InlineKeyboardButton("نمایش دوباره لیست", callback_data="100"),
            ]
        ]
        query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))

    if choice == 101:
        text = """*صفحه راهنما* 
◀ برای دیدن لیست ارز ها روی _ارزها_ کلیک کنید
◀ اسم ارز یا کشور دلخواه را مستقیما برای ربات ارسال کنید *به زودی*
◀ برای استفاده از inline query، در قسمت چت، ایدی بات را وارد کنید (@hoorchibot) و ارز مورد نظر را انتخاب کنید تا ارسال شود
""" 
        currency_keyboard = ([InlineKeyboardButton("ارز ها", callback_data="100")],)

        query.edit_message_text(text, parse_mode="Markdown")
        query.edit_message_reply_markup(InlineKeyboardMarkup(currency_keyboard))


def message_handler(update: Update, context: CallbackQueryHandler):
    text = update["message"]["text"]
    if text == "🏠":
        update.message.reply_text(
            text="منوی اصلی🏠", reply_markup=InlineKeyboardMarkup(main_keyboard)
        )
    else:
        reply_markup = ReplyKeyboardMarkup(
            [["🏠"]],
            one_time_keyboard=True,
            resize_keyboard=True,
            input_field_placeholder="برای دیدن منوی اصلی کلیک کنید",
        )
        update.message.reply_text(
            "برای دیدن منوی اصلی کلیک کنید", reply_markup=reply_markup
        )


class MyThread(Thread):
    def __init__(self, event):
        Thread.__init__(self)
        self.stopped = event

    def run(self):
        while not self.stopped.wait(180):
            update_db()


def main() -> None:
    updater = Updater(TOKEN)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text, message_handler))
    dp.add_handler(InlineQueryHandler(inlinequery))
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url="https://hoorchibot.herokuapp.com/" + TOKEN,
    )
    stop_flag = Event()
    thread = MyThread(stop_flag)
    thread.start()
    # updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
