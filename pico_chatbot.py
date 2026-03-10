import os
import time
import subprocess
import sys
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
from WhisPlay import WhisPlayBoard

# --- CLI executables and model paths ---
# Make sure these are in your PATH or provide full paths
WHISPER_CLI = "whisper-cli"
PICOLM_CLI = "picolm"
PIPER_CLI = "piper/piper"

WHISPER_MODEL = os.path.join(os.getcwd(), "models", "ggml-tiny.en.bin")
PICOLM_MODEL = os.path.join(os.getcwd(), "models", "smollm2-model-q4_0.gguf")
PIPER_CONFIG = os.path.join(os.getcwd(), "piper", "config.json")
PIPER_MODEL = os.path.join(os.getcwd(), "piper", "model.onnx")

RECORD_FILE = os.path.join(os.getcwd(), "in.wav")
MAX_RECORD_SEC = 5

# --- State Machine ---
class State:
    IDLE = 0
    BUSY = 1

def get_card_index():
    cmd = "cat /proc/asound/cards 2>/dev/null | grep -i wm8960 | head -1 | awk '{print $1}'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

# --- LCD Screen Generation (Taken from Whisplay Demo) ---
def make_text_image(text, sub_text="", bg_color=(0, 0, 0), text_color=(255, 255, 255),
                    width=240, height=280):
    """Generate RGB565 pixel data with text (for LCD display)"""
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load font, fall back to default
    font_large = None
    font_small = None
    for fpath in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]:
        if os.path.exists(fpath):
            try:
                font_large = ImageFont.truetype(fpath, 28)
                font_small = ImageFont.truetype(fpath, 18)
            except Exception:
                pass
            break

    if font_large is None:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Center main text
    bbox = draw.textbbox((0, 0), text, font=font_large)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2 - 15
    draw.text((x, y), text, fill=text_color, font=font_large)

    # Sub text
    if sub_text:
        bbox2 = draw.textbbox((0, 0), sub_text, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        x2 = (width - tw2) // 2
        draw.text((x2, y + th + 15), sub_text, fill=text_color, font=font_small)

    # Convert to RGB565
    pixel_data = []
    for py in range(height):
        for px in range(width):
            r, g, b = img.getpixel((px, py))
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
    return pixel_data

def load_image_rgb565(filepath, screen_width=240, screen_height=280):
    """Load image file as RGB565 pixel data (scale maintaining aspect ratio + center crop)"""
    try:
        img = Image.open(filepath).convert('RGB')
        original_width, original_height = img.size
        aspect_ratio = original_width / original_height
        screen_aspect_ratio = screen_width / screen_height

        if aspect_ratio > screen_aspect_ratio:
            new_height = screen_height
            new_width = int(new_height * aspect_ratio)
            resized_img = img.resize((new_width, new_height))
            offset_x = (new_width - screen_width) // 2
            cropped_img = resized_img.crop(
                (offset_x, 0, offset_x + screen_width, screen_height))
        else:
            new_width = screen_width
            new_height = int(new_width / aspect_ratio)
            resized_img = img.resize((new_width, new_height))
            offset_y = (new_height - screen_height) // 2
            cropped_img = resized_img.crop(
                (0, offset_y, screen_width, offset_y + screen_height))

        pixel_data = []
        for py in range(screen_height):
            for px in range(screen_width):
                r, g, b = cropped_img.getpixel((px, py))
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
        return pixel_data
    except Exception:
        return None
    
def update_screen(board, text, sub_text="", color="cyan"):
    if color.lower() == "blue":
        text_color = (100, 180, 255)
    elif color.lower() == "red":
        text_color = (255, 49, 49)
    elif color.lower() == "yellow":
        text_color = (253, 218, 13)
    else:
        text_color = (0, 255, 255)
    w, h = board.LCD_WIDTH, board.LCD_HEIGHT
    # generate pixel data from text
    pixel_data = make_text_image(text, sub_text, text_color=text_color, width=w, height=h)
    try:
        # show on screen
        board.draw_image(0, 0, w, h, pixel_data)
    except Exception as e:
        print(f"Error updating screen: {e}")

def start_recording(board):
    hw_device = f"hw:{get_card_index()},0"

    # Use 48000Hz — RK3566 I2S PLL can generate clean 12.288MHz MCLK for 48000Hz
    # 44100Hz requires 11.2896MHz, RK3566 PLL cannot divide precisely, causing clock jitter and distortion
    record_proc = subprocess.Popen(
        ['arecord', '-D', hw_device, '-f', 'S16_LE', '-r', '48000',
            '-c', '2', '-t', 'wav', '-d', str(MAX_RECORD_SEC), RECORD_FILE],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
    record_proc.wait(timeout=MAX_RECORD_SEC + 5)  # Wait for recording to finish with some buffer

    # Check if recording file was generated
    if not os.path.exists(RECORD_FILE) or os.path.getsize(RECORD_FILE) < 100:
        print("⚠️  Recording file is empty or not generated")
        update_screen(board, "Error: Recording was not saved.")

# --- Main Logic ---
def chat_loop():
    board = WhisPlayBoard()
    board.set_backlight(60)
    curr_state = State.IDLE

    update_screen(board, "Ready!\nHold button to talk.")
    while True:
        if board.button_pressed():
            curr_state = State.BUSY
            update_screen(board, "Listening for 5 seconds...", color="blue")
            
            # RECORD
            start_recording(board)
            
            # TRANSCRIBE (Whisper.cpp)
            update_screen(board, "Thinking...")
            time.sleep(1) # Small delay to ensure file is ready
            user_text = subprocess.check_output(" ".join([WHISPER_CLI, "-m", WHISPER_MODEL, "-nt", "-f", RECORD_FILE]), text=True, shell=True)
            
            # GENERATE (PicoLM)
            # We run this and capture output to display it
            ai_response = subprocess.check_output(" ".join([PICOLM_CLI, "-m", PICOLM_MODEL, "-p", f"User: {user_text}\nAssistant:"]), text=True, shell=True)
            
            # DISPLAY & SPEAK (Piper)
            update_screen(board, f"AI: {ai_response}")
            
            # Speak the text using Piper
            piper_cmd = f"echo '{ai_response}' | {PIPER_CLI} --model {PIPER_MODEL} --output_raw | aplay -r 22050 -f S16_LE -t raw"
            subprocess.Popen(piper_cmd, shell=True)
            
            time.sleep(1) # Debounce
        else:
            if curr_state == State.BUSY:
                update_screen(board, "Ready!\nHold button to talk.")
                curr_state = State.IDLE

try:
    chat_loop()
except KeyboardInterrupt:
    GPIO.cleanup()
    sys.exit(0)
