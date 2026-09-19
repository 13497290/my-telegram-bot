# my-telegram-bot
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from groq import Groq
from supabase import create_client, Client

# Logging configuration
logging.basicConfig(level=logging.INFO)

# ================= Configuration =================
# Render.com ပေါ်ရောက်ရင် Environment Variables ထဲမှာ Key တွေ ထည့်ပေးရပါမည်
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nrcggomqpgjslxjaiudw.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@aistudy1239874")

# Clients Initializing
groq_client = Groq(api_key=GROQ_API_KEY)
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= System Prompt =================
SYSTEM_PROMPT = """
You are an expert Prompt Engineer. The user will provide an idea in Myanmar or English.
Transform it into a highly effective, structured prompt for Midjourney, ChatGPT, or Suno AI.

Output Format:
1. Optimized Prompt (in English): [Copy-paste ready prompt]
2. Brief Explanation (in Myanmar): [၁ ကြောင်းစာ အနှစ်ချုပ် ရှင်းလင်းချက်]
"""

# ================= Helper Functions =================
async def check_channel_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Force Channel Join စစ်ဆေးခြင်း"""
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_or_create_user(user_id: int, username: str, referrer_id: int = None):
    """Database တွင် User ရှိ/မရှိ စစ်ပြီး အသစ်ဆောက်ခြင်း"""
    response = supabase_client.table("telegram_users").select("*").eq("telegram_id", user_id).execute()
    
    if not response.data:
        # User အသစ်ဆောက်မည်
        user_data = {
            "telegram_id": user_id,
            "username": username,
            "daily_credits": 8,
            "is_premium": False
        }
        supabase_client.table("telegram_users").insert(user_data).execute()
        
        # Self-Referral စစ်ဆေးခြင်းနှင့် Referral Record မှတ်ခြင်း
        if referrer_id and referrer_id != user_id:
            supabase_client.table("referrals").insert({
                "referrer_id": referrer_id,
                "referee_id": user_id,
                "status": "pending"
            }).execute()
            
        return user_data, True
    return response.data[0], False

# ================= Bot Handlers =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = int(args[0]) if args and args[0].isdigit() else None
    
    user_data, is_new = get_or_create_user(user.id, user.username, referrer_id)
    
    # Check Channel Join
    is_joined = await check_channel_member(user.id, context)
    if not is_joined:
        keyboard = [[InlineKeyboardButton("📢 Channel သို့ Join ရန်", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        await update.message.reply_text(
            f"❌ Bot ကို အသုံးပြုရန်အတွက် ကျေးဇူးပြု၍ ကျွန်ုပ်တို့၏ {CHANNEL_USERNAME} Channel သို့ မဖြစ်မနေ Join ပေးပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.id}"
    
    welcome_text = (
        f"မင်္ဂလာပါ {user.first_name}! 👋\n\n"
        f"🤖 **Prompt Helper Bot** မှ ကြိုဆိုပါတယ်။\n"
        f"သင်ဖြစ်စေချင်သော အိုင်ဒီယာကို ရိုက်ထည့်ပါ၊ AI Prompt အဖြစ် ပြောင်းပေးပါမည်။\n\n"
        f"💳 လက်ရှိ ကျန်ရှိသော Credit: **{user_data['daily_credits']} Credits**\n\n"
        f"🔗 သင့်၏ Referral Link:\n`{ref_link}`\n"
        f"(သူငယ်ချင်း ၁ ယောက် ဖိတ်ရင် **+5 Credits** ရပါမည်)"
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def process_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text
    
    # Channel Join စစ်ဆေးခြင်း
    if not await check_channel_member(user.id, context):
        await update.message.reply_text(f"⚠️ ကျေးဇူးပြု၍ {CHANNEL_USERNAME} Channel သို့ အရင် Join ပါ။")
        return

    # User Credits စစ်ဆေးခြင်း
    user_res = supabase_client.table("telegram_users").select("*").eq("telegram_id", user.id).execute()
    if not user_res.data:
        get_or_create_user(user.id, user.username)
        user_data = {"daily_credits": 8, "is_premium": False}
    else:
        user_data = user_res.data[0]

    credits = user_data["daily_credits"]
    is_premium = user_data["is_premium"]

    if not is_premium and credits <= 0:
        await update.message.reply_text(
            "❌ ယနေ့အတွက် အခမဲ့ 8 Credits ကုန်သွားပါပြီ။\n\n"
            "သူငယ်ချင်းများကို ဖိတ်ခေါ်၍ +5 Credits အပိုယူပါ သို့မဟုတ် Premium သို့ အဆင့်မြှင့်ပါ။"
        )
        return

    # Groq API ခေါ်ယူခြင်း
    await update.message.reply_text("⏳ Prompt ထုတ်ပေးနေပါသည်...")
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.7
        )
        output = completion.choices[0].message.content
        
        # Credit ၁ ခု လျှော့ခြင်း (Premium မဟုတ်ပါက)
        if not is_premium:
            supabase_client.table("telegram_users").update({"daily_credits": credits - 1}).eq("telegram_id", user.id).execute()
        
        # Anti-Hack Referral Claim Trigger (ပထမဆုံး ရိုက်ခြင်းဖြစ်ပါက Referrer ထံ +5 Credit ပေးမည်)
        try:
            supabase_client.rpc("claim_referral_reward", {"p_referee_id": user.id}).execute()
        except Exception:
            pass

        await update.message.reply_text(output)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error ဖြစ်ပွားပါသည်: {str(e)}")

# ================= Main App =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_prompt))
    
    print("Bot is running...")
    app.run_polling()
