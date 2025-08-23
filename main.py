import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import google.generativeai as genai
from keep_alive import keep_alive
import time

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Configure the Google Gemini API
try:
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Error configuring Google AI: {e}")
    model = None

# Dictionary to store conversation history
conversation_history = {}

# Bot setup
handler = logging.FileHandler(filename='discord.log',
                              encoding='utf-8',
                              mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    activity = discord.CustomActivity(name="Use /talk to begin a conversation",
                                      emoji="💬")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
    print(f"{bot.user.name} is Online and ready to talk!")


async def ai_therapist_response(user_id, user_message):
    if not model:
        return "Sorry, the AI service is not configured correctly."

    history = conversation_history.get(user_id, [])
    full_prompt = "\n".join(history) + f"\nUser: {user_message}"

    try:
        system_prompt = (
            "You are an AI Therapeutic Coach. Your goal is to help users explore their own thoughts and feelings "
            "using techniques based on Cognitive Behavioral Therapy (CBT) and Socratic questioning. Give direct advice or solutions. "
            "Instead, ask open-ended, guiding questions to help the user challenge their own thought patterns. "
            "For example, ask 'What evidence supports that thought?', 'Is there another way to look at this situation?', "
            "or 'What would you tell a friend who was in your shoes?'. Maintain a compassionate, supportive, and non-judgmental tone. "
            "Remember the past conversation for context. Provide medical advice and always operate as a supportive tool, not a replacement for a therapist."
        )
        generation_config = genai.GenerationConfig(temperature=0.7)
        response = await model.generate_content_async(
            f"{system_prompt}\n\n{full_prompt}",
            generation_config=generation_config)

        history.append(f"User: {user_message}")
        history.append(f"Bot: {response.text}")
        conversation_history[user_id] = history[-10:]

        return response.text
    except Exception as e:
        print(f"A Google AI error occurred: {e}")
        return "Sorry, I couldn't connect to the AI service at the moment."


@bot.tree.command(
    name="talk",
    description="Get a supportive, therapist-style reply from the AI.")
async def talk_slash(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    response = await ai_therapist_response(interaction.user.id, message)
    disclaimer = (
        "\n\n---\n*Please note: I am an AI assistant, not a licensed therapist. "
        "If you are in crisis, please reach out to a mental health professional or a helpline immediately.*"
    )
    full_message = response + disclaimer
    if len(full_message) <= 2000:
        await interaction.followup.send(full_message)
    else:
        chunks = [
            full_message[i:i + 2000] for i in range(0, len(full_message), 2000)
        ]
        for chunk in chunks:
            await interaction.followup.send(chunk)


@bot.tree.command(name="dmme",
                  description="Have the bot send you a DM for a private chat.")
async def dmme_slash(interaction: discord.Interaction):
    try:
        await interaction.user.send(
            "Hello, I'm glad you're here. This is a private space to talk. "
            "Feel free to begin whenever you're ready.")
        await interaction.response.send_message(
            "I've started a private conversation with you in your DMs.",
            ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            "I couldn't send you a DM. Please check your privacy settings to allow DMs from server members.",
            ephemeral=True)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            response = await ai_therapist_response(message.author.id,
                                                   message.content)
            disclaimer = (
                "\n\n---\n*Please note: I am an AI assistant, not a licensed therapist. "
                "If you are in crisis, please reach out to a mental health professional or a helpline immediately.*"
            )
            full_message = response + disclaimer
            if len(full_message) <= 2000:
                await message.channel.send(full_message)
            else:
                chunks = [
                    full_message[i:i + 2000]
                    for i in range(0, len(full_message), 2000)
                ]
                for chunk in chunks:
                    await message.channel.send(chunk)


while True:
    try:
        keep_alive()
        if token:
            bot.run(token, log_handler=handler, log_level=logging.DEBUG)
        else:
            print("FATAL: DISCORD_TOKEN not found in environment variables.")
            break  # Exit if the token is missing
    except discord.errors.ConnectionClosed:
        print("Connection to Discord closed. Reconnecting...")
        time.sleep(5)  # Wait 5 seconds before trying to reconnect
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Restarting the bot in 10 seconds...")
        time.sleep(10)  # Wait 10 seconds before restarting
