import discord
import random
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

games = {}

LOCATIONS = [
    "المستشفى", "المطار", "الشاطئ", "المدرسة", "المطعم",
    "القطار", "الفضاء", "البنك", "الجيش", "السينما",
    "الملعب", "السوبر ماركت", "الفندق", "المصنع", "السجن"
]

QUESTION_TIME = 60  # ثواني لكل سؤال

def get_game(guild_id):
    if guild_id not in games:
        games[guild_id] = {
            "players": [],
            "started": False,
            "location": None,
            "spy": None,
            "round": 0,
            "total_rounds": 0,
            "channel": None,
            "votes": {},
            "waiting_answer": False,
            "questioner": None,
            "questioned": None,
            "question_task": None,
            "game_task": None
        }
    return games[guild_id]

def reset_game(guild_id):
    game = games.get(guild_id, {})
    # الغي أي tasks شغالة
    if game.get("question_task"):
        game["question_task"].cancel()
    if game.get("game_task"):
        game["game_task"].cancel()
    games[guild_id] = {
        "players": [],
        "started": False,
        "location": None,
        "spy": None,
        "round": 0,
        "total_rounds": 0,
        "channel": None,
        "votes": {},
        "waiting_answer": False,
        "questioner": None,
        "questioned": None,
        "question_task": None,
        "game_task": None
    }

async def run_game(guild_id):
    game = games[guild_id]
    channel = game["channel"]
    total_rounds = game["total_rounds"]

    for round_num in range(1, total_rounds + 1):
        if not game["started"]:
            return

        game["round"] = round_num

        # اختيار عشوائي مين يسأل مين
        questioner = random.choice(game["players"])
        remaining = [p for p in game["players"] if p != questioner]
        questioned = random.choice(remaining)
        game["questioner"] = questioner
        game["questioned"] = questioned
        game["waiting_answer"] = False

        await channel.send(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 **الجولة {round_num} من {total_rounds}**\n\n"
            f"🗣️ {questioner.mention} **يسأل** {questioned.mention}\n"
            f"⏱️ عندك **{QUESTION_TIME} ثانية** تسأل!\n\n"
            f"لما تخلص من السؤال والجواب اكتب **خلص** ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        # استنى الـ questioner يكتب "خلص" أو ينتهي الوقت
        game["waiting_answer"] = True
        try:
            task = asyncio.ensure_future(
                wait_for_done(guild_id, questioner)
            )
            game["question_task"] = task
            await asyncio.wait_for(asyncio.shield(task), timeout=QUESTION_TIME)
        except asyncio.TimeoutError:
            if game["started"]:
                await channel.send(
                    f"⏰ **انتهى الوقت!**\n"
                    f"{questioner.mention} خلص وقته ⌛"
                )
        except asyncio.CancelledError:
            return

        game["waiting_answer"] = False
        await asyncio.sleep(2)

    if not game["started"]:
        return

    # خلصت الجولات — وقت التصويت
    await channel.send(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏁 **خلصت كل الجولات!**\n\n"
        f"🗳️ دلوقتي وقت التصويت!\n"
        f"كل واحد يكتب: `!تصويت @اسم`\n"
        f"لما الكل يصوّت اكتب `!نتيجة`\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

async def wait_for_done(guild_id, questioner):
    while True:
        await asyncio.sleep(0.5)
        game = games.get(guild_id)
        if not game or not game["waiting_answer"]:
            return

@client.event
async def on_ready():
    print(f"✅ البوت شغال: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    guild_id = message.guild.id if message.guild else None
    if not guild_id:
        return

    game = get_game(guild_id)
    content = message.content.strip()

    # ===== خلص =====
    if content == "خلص":
        if not game["started"] or not game["waiting_answer"]:
            return
        if message.author == game["questioner"]:
            game["waiting_answer"] = False
            await message.channel.send(f"✅ **{message.author.display_name}** خلص! جاي الدور الجاي...")

    # ===== !مساعدة =====
    elif content == "!مساعدة":
        await message.channel.send("""
🎮 **أوامر لعبة بره السالفة**

`!انضم` — سجّل اسمك
`!لاعبين` — شوف المسجلين
`!ابدأ` — ابدأ اللعبة (3 لاعبين على الأقل)
`!تصويت @اسم` — صوّت على الجاسوس
`!نتيجة` — اكشف الجاسوس
`!كسب_ناس` — الناس كسبوا
`!كسب_جاسوس` — الجاسوس كسب
`!ريست` — امسح اللعبة
`خلص` — لما تخلص من السؤال والجواب
""")

    # ===== !انضم =====
    elif content == "!انضم":
        if game["started"]:
            await message.channel.send("⛔ اللعبة بدأت! استنى الجولة الجاية.")
            return
        if message.author in game["players"]:
            await message.channel.send(f"⚠️ {message.author.display_name} انت مسجل بالفعل!")
            return
        game["players"].append(message.author)
        count = len(game["players"])
        await message.channel.send(
            f"✅ **{message.author.display_name}** انضم!\n"
            f"👥 عدد اللاعبين: **{count}**\n"
            f"{'✔️ ممكن تبدأ بـ `!ابدأ`' if count >= 3 else f'⏳ محتاج {3-count} لاعب تاني'}"
        )

    # ===== !لاعبين =====
    elif content == "!لاعبين":
        if not game["players"]:
            await message.channel.send("😶 مفيش لاعبين. اكتب `!انضم`!")
            return
        names = "\n".join([f"🎮 {p.display_name}" for p in game["players"]])
        await message.channel.send(f"**👥 اللاعبين ({len(game['players'])}):**\n{names}")

    # ===== !ابدأ =====
    elif content == "!ابدأ":
        if game["started"]:
            await message.channel.send("⚠️ اللعبة بدأت بالفعل!")
            return
        if len(game["players"]) < 3:
            await message.channel.send(f"❌ محتاج 3 لاعبين! عندك {len(game['players'])} بس.")
            return

        await message.channel.send(
            f"⚙️ **كم جولة أسئلة عايزين؟**\n"
            f"ابعت رقم من **1** لـ **10** 🔢"
        )
        game["waiting_rounds"] = True

    # ===== اختيار عدد الجولات =====
    elif game.get("waiting_rounds") and content.isdigit():
        rounds = int(content)
        if rounds < 1 or rounds > 10:
            await message.channel.send("⚠️ ابعت رقم من 1 لـ 10 بس!")
            return

        game["waiting_rounds"] = False
        game["started"] = True
        game["total_rounds"] = rounds
        game["location"] = random.choice(LOCATIONS)
        game["spy"] = random.choice(game["players"])
        game["channel"] = message.channel
        game["votes"] = {}

        # بعث الأدوار بالـ DM
        failed = []
        for player in game["players"]:
            try:
                if player == game["spy"]:
                    await player.send(
                        "🕵️ **أنت الجاسوس!**\n\n"
                        "مش عارف المكان، حاول تعرفه من الأسئلة!\n"
                        "لو حدست صح بـ `!مكان المكان` قبل ما يكشفوك، كسبت 🏆"
                    )
                else:
                    await player.send(
                        f"📍 **المكان هو: {game['location']}**\n\n"
                        "فيه جاسوس مش عارف المكان!\n"
                        "اسأل أسئلة ذكية تكشفه 🧠"
                    )
                await message.channel.send(
                    f"📩 {player.mention} اتبعتلك رسالة سرية — افتح الـ DM!"
                )
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                failed.append(player.display_name)

        players_list = ", ".join([p.display_name for p in game["players"]])
        await message.channel.send(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎮 **اللعبة بدأت!**\n"
            f"👥 اللاعبين: {players_list}\n"
            f"🔄 عدد الجولات: **{rounds}**\n"
            f"⏱️ وقت كل سؤال: **{QUESTION_TIME} ثانية**\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        await asyncio.sleep(3)
        task = asyncio.ensure_future(run_game(guild_id))
        game["game_task"] = task

    # ===== !مكان (الجاسوس يحدس) =====
    elif content.startswith("!مكان "):
        if not game["started"]:
            return
        if message.author != game["spy"]:
            await message.channel.send("⚠️ بس الجاسوس يقدر يستخدم الأمر ده!")
            return
        guess = content[7:].strip()
        if guess == game["location"]:
            await message.channel.send(
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"😈 **الجاسوس حدس المكان الصح!**\n\n"
                f"🕵️ الجاسوس: **{game['spy'].display_name}**\n"
                f"📍 المكان كان: **{game['location']}**\n\n"
                f"🏆 **الجاسوس كسب!**\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await game["spy"].send(f"🏆 **مبروك!** حدست المكان الصح وكسبت! 🎉")
            except:
                pass
            if game.get("game_task"):
                game["game_task"].cancel()
            await message.channel.send("🔄 اكتب `!ريست` للعبة جديدة!")
            reset_game(guild_id)
        else:
            await message.channel.send(
                f"❌ **{message.author.display_name}** حدس **{guess}** — غلط!\n"
                f"🕵️ الجاسوس انكشف!"
            )

    # ===== !تصويت =====
    elif content.startswith("!تصويت"):
        if not game["started"]:
            await message.channel.send("❌ اللعبة مش بدأت!")
            return
        if not message.mentions:
            await message.channel.send("⚠️ مثال: `!تصويت @اسم`")
            return
        target = message.mentions[0]
        if target not in game["players"]:
            await message.channel.send("⚠️ الشخص ده مش في اللعبة!")
            return
        game["votes"][message.author.id] = target
        votes_count = {}
        for v in game["votes"].values():
            votes_count[v.display_name] = votes_count.get(v.display_name, 0) + 1
        votes_display = "\n".join([f"• {n}: {c} صوت" for n, c in votes_count.items()])
        await message.channel.send(
            f"🗳️ **{message.author.display_name}** صوّت على **{target.display_name}**\n\n"
            f"**الأصوات:**\n{votes_display}\n\n"
            f"صوّت {len(game['votes'])} من {len(game['players'])}\n"
            f"اكتب `!نتيجة` لكشف الجاسوس!"
        )

    # ===== !نتيجة =====
    elif content == "!نتيجة":
        if not game["started"] or not game["votes"]:
            await message.channel.send("❌ مفيش أصوات لسه!")
            return
        votes_count = {}
        for v in game["votes"].values():
            votes_count[v] = votes_count.get(v, 0) + 1
        accused = max(votes_count, key=votes_count.get)
        spy = game["spy"]
        location = game["location"]
        if accused == spy:
            await message.channel.send(
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎉 **الناس كشفوا الجاسوس!**\n\n"
                f"🕵️ الجاسوس كان: **{spy.display_name}**\n"
                f"📍 المكان كان: **{location}**\n\n"
                f"🏆 **مبروك للاعبين!**\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            for w in [p for p in game["players"] if p != spy]:
                try:
                    await w.send(f"🏆 **مبروك {w.display_name}!** كشفتوا الجاسوس! 🎉")
                except:
                    pass
        else:
            await message.channel.send(
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"😈 **الجاسوس نجا!**\n\n"
                f"🕵️ الجاسوس كان: **{spy.display_name}**\n"
                f"📍 المكان كان: **{location}**\n\n"
                f"🏆 **مبروك للجاسوس!**\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await spy.send(f"😈 **مبروك {spy.display_name}!** نجحت تخدعهم! 🏆")
            except:
                pass
        if game.get("game_task"):
            game["game_task"].cancel()
        await message.channel.send("🔄 اكتب `!ريست` للعبة جديدة!")
        reset_game(guild_id)

    # ===== !كسب_ناس =====
    elif content == "!كسب_ناس":
        if not game["started"]:
            return
        spy = game["spy"]
        location = game["location"]
        winners = [p for p in game["players"] if p != spy]
        await message.channel.send(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 **الناس كسبوا!**\n"
            f"🕵️ الجاسوس: **{spy.display_name}**\n"
            f"📍 المكان: **{location}**\n"
            f"🏆 **مبروك:** {', '.join([w.display_name for w in winners])}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        for w in winners:
            try:
                await w.send(f"🏆 **مبروك {w.display_name}!** 🎉")
            except:
                pass
        if game.get("game_task"):
            game["game_task"].cancel()
        await message.channel.send("🔄 اكتب `!ريست` للعبة جديدة!")
        reset_game(guild_id)

    # ===== !كسب_جاسوس =====
    elif content == "!كسب_جاسوس":
        if not game["started"]:
            return
        spy = game["spy"]
        location = game["location"]
        await message.channel.send(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"😈 **الجاسوس كسب!**\n"
            f"🕵️ الجاسوس: **{spy.display_name}**\n"
            f"📍 المكان: **{location}**\n"
            f"🏆 **مبروك {spy.display_name}!**\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            await spy.send(f"😈 **مبروك!** نجحت تخدعهم! 🏆")
        except:
            pass
        if game.get("game_task"):
            game["game_task"].cancel()
        await message.channel.send("🔄 اكتب `!ريست` للعبة جديدة!")
        reset_game(guild_id)

    # ===== !ريست =====
    elif content == "!ريست":
        reset_game(guild_id)
        await message.channel.send(
            "🔄 **اتمسحت اللعبة!**\n"
            "1️⃣ `!انضم` للتسجيل\n"
            "2️⃣ `!ابدأ` لما يكملوا 3+"
        )

client.run(os.environ['TOKEN'])
