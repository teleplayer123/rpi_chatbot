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

def wrap_text(draw, text, font, max_width):
    """Split text into lines that fit within max_width."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test_line = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]

        if w <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines

def make_multiline_text_image(
    text,
    sub_text="",
    bg_color=(0, 0, 0),
    text_color=(255, 255, 255),
    width=240,
    height=280,
):
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_large = None
    font_small = None
    for fpath in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
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

    padding = 10
    max_text_width = width - padding * 2

    # ---- Wrap main text ----
    lines = wrap_text(draw, text, font_large, max_text_width)

    # Measure total height
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_large)
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 6
    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Start Y (centered)
    y = (height - total_text_height) // 2 - (10 if sub_text else 0)

    # Draw each line centered
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_large)
        w = bbox[2] - bbox[0]

        x = (width - w) // 2
        draw.text((x, y), line, fill=text_color, font=font_large)

        y += line_heights[i] + line_spacing

    # ---- Subtext ----
    if sub_text:
        sub_lines = wrap_text(draw, sub_text, font_small, max_text_width)

        y += 10  # gap

        for line in sub_lines:
            bbox = draw.textbbox((0, 0), line, font=font_small)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]

            x = (width - w) // 2
            draw.text((x, y), line, fill=text_color, font=font_small)
            y += h + 4

    # ---- Convert to RGB565 ----
    pixel_data = []
    for py in range(height):
        for px in range(width):
            r, g, b = img.getpixel((px, py))
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])

    return pixel_data
    
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
    pixel_data = make_multiline_text_image(text, sub_text, text_color=text_color, width=w, height=h)
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
        print("Recording file is empty or not generated")
        update_screen(board, "Error: Recording was not saved.")

# --- Main Logic ---
def chat_loop():
    board = WhisPlayBoard()
    board.set_backlight(60)
    curr_state = State.IDLE

    update_screen(board, "READY", sub_text="Press button to talk.")
    while True:
        if board.button_pressed():
            curr_state = State.BUSY
            update_screen(board, "Listening...", color="blue")
            
            # RECORD
            start_recording(board)
            
            # TRANSCRIBE (Whisper.cpp)
            update_screen(board, "Thinking...", color="blue")
            time.sleep(1) # Small delay to ensure file is ready
            user_text = subprocess.check_output(" ".join([WHISPER_CLI, "-m", WHISPER_MODEL, "-nt", "-f", RECORD_FILE]), text=True, shell=True)

            # Display user prompt
            update_screen(board, "User: ", sub_text=user_text, color="yellow")
            time.sleep(3) # Show user input for a moment

            # GENERATE (PicoLM)
            # We run this and capture output to display it
            ai_response = subprocess.check_output(" ".join([PICOLM_CLI, PICOLM_MODEL, "-p", f"\"{user_text.strip()}\""]), text=True, shell=True)
            
            # DISPLAY & SPEAK (Piper)
            update_screen(board, "AI: ", sub_text=ai_response)
            time.sleep(5) # Show AI response for a moment

            # Speak the text using Piper
            piper_cmd = f"echo '{ai_response}' | {PIPER_CLI} --model {PIPER_MODEL} --config {PIPER_CONFIG} --output_raw | aplay -r 22050 -f S16_LE -t raw"
            subprocess.Popen(piper_cmd, shell=True)
            
            time.sleep(1) # Debounce
        else:
            if curr_state == State.BUSY:
                update_screen(board, "READY", sub_text="Press button to talk.")
                curr_state = State.IDLE

try:
    chat_loop()
except KeyboardInterrupt:
    GPIO.cleanup()
    sys.exit(0)
