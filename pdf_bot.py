import os
import logging
from datetime import datetime
import img2pdf
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
user_data = {}

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming images with size check."""
    chat_id = update.message.chat_id
    
    try:
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        elif update.message.document and update.message.document.mime_type.startswith('image/'):
            file = await update.message.document.get_file()
        else:
            await update.message.reply_text('Please send an image (photo or document).')
            return

        # Check file size
        if file.file_size > MAX_FILE_SIZE:
            await update.message.reply_text('❌ Image exceeds 5MB limit!')
            return

        # Create user directory
        user_dir = os.path.join('temp', str(chat_id))
        os.makedirs(user_dir, exist_ok=True)

        # Download image
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        file_name = os.path.join(user_dir, f"{timestamp}.jpg")
        await file.download_to_drive(file_name)

        # Update user_data
        if chat_id not in user_data:
            user_data[chat_id] = {'images': [], 'message_id': None}
        
        user_data[chat_id]['images'].append(file_name)
        count = len(user_data[chat_id]['images'])

        # Send or update message
        if count == 1:
            msg = await update.message.reply_text('✅ First image received! Send more or /generate')
            user_data[chat_id]['message_id'] = msg.message_id
        else:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=user_data[chat_id]['message_id'],
                    text=f'📚 Total images: {count}\nSend more or /generate'
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                # If message editing fails, send new message
                msg = await update.message.reply_text(f'📚 Total images: {count}\nSend more or /generate')
                user_data[chat_id]['message_id'] = msg.message_id
        
    except Exception as e:
        logger.error(f"Error handling image: {e}")
        await update.message.reply_text('⚠️ Failed to process image')

# ... (keep other functions the same as original code)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        '📸 Send me images (as photos/documents), then use /generate to create PDF. '
        'Use /cancel to clear images.\n'
        'Max file size: 5MB per image'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await update.message.reply_text(
        'How to use:\n'
        '1. Send images (as photos or documents)\n'
        '2. Use /generate to create PDF\n'
        '3. Use /cancel to start over\n\n'
        '⚠️ Max 5MB per image'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user's images"""
    chat_id = update.message.chat_id
    if chat_id in user_data:
        # Delete temporary files
        for file_path in user_data[chat_id]['images']:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
        del user_data[chat_id]
        await update.message.reply_text('🗑 All images cleared!')
    else:
        await update.message.reply_text('No images to clear.')

async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate PDF from collected images."""
    chat_id = update.message.chat_id
    if chat_id not in user_data or not user_data[chat_id]['images']:
        await update.message.reply_text('No images received yet. Send some images first.')
        return

    # Create PDF
    images = user_data[chat_id]['images']
    pdf_path = os.path.join('temp', str(chat_id), 'output.pdf')
    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(images))
    except Exception as e:
        logger.error(f"PDF conversion error: {e}")
        await update.message.reply_text('Failed to create PDF. Please try again.')
        return

    # Send PDF
    await update.message.reply_document(
        document=open(pdf_path, 'rb'),
        filename='images.pdf'
    )

    # Cleanup
    for file_path in images:
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error deleting {file_path}: {e}")
    os.remove(pdf_path)
    del user_data[chat_id]

def main():
    """Start the bot."""
    token = "7917059408:AAHpv6tjDZHjhojy0PQqtOA8J8wWWc3pIVs"
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env file")

    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate", generate_pdf))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    application.run_polling()

if __name__ == '__main__':
    os.makedirs('temp', exist_ok=True)
    main()