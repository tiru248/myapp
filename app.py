import os, json, csv, re, io, zipfile
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, send_from_directory
from flask import request, redirect, url_for, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops
from bs4 import BeautifulSoup
import cv2
import sys
import numpy as np
from io import BytesIO
import mediapipe as mp
from rembg import remove
from pathlib import Path
from math import ceil
import base64
import shutil
from werkzeug.utils import secure_filename
import glob
import itertools 
from flask import after_this_request
from werkzeug.utils import secure_filename


from flask import Flask
app = Flask(__name__)

os.environ["NUMBA_DISABLE_CACHE"] = "1"
import os
os.environ["NUMBA_CACHE_DIR"] = os.path.join(os.getcwd(), "numba_cache")

Image.MAX_IMAGE_PIXELS = None
mp_face_mesh = mp.solutions.face_mesh

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    WORK_DIR = os.path.dirname(sys.executable)  # location where .exe runs
else:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    WORK_DIR = base_dir

counter = 1
# 🟢 STATIC & TEMPLATES for reading only
# Working directory for writing files
TEMPLATE_FOLDER = os.path.join(base_dir, "templates")
STATIC_FOLDER = os.path.join(base_dir, "static")
LAYOUT_JSON_PATH = os.path.join(STATIC_FOLDER, "layout.json")
from flask import Flask
app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
CAPTURE_FOLDER = os.path.join(base_dir, 'static', 'captured')
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, "uploads")
CLEANED_FOLDER = os.path.join(WORK_DIR, "cleaned")
CAPTURE_DIR = os.path.join(WORK_DIR, "captured")
PHOTO_FOLDER = os.path.join(WORK_DIR, "photos")
CSV_FILE = os.path.join(STATIC_FOLDER, "students.csv")
MASK_PATH = os.path.join(UPLOAD_FOLDER, "mask.png")
ZIP_PATH = os.path.join(base_dir, 'captured_photos.zip')
CLEANED_FOLDER = "static/cleaned"
# Ensure all folders exist
os.makedirs(STATIC_FOLDER, exist_ok=True)
os.makedirs(PHOTO_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)
os.makedirs(CAPTURE_DIR, exist_ok=True)
os.makedirs(CAPTURE_FOLDER, exist_ok=True)
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
counter = itertools.count(1) 
app = Flask(__name__)





try:
    with open(LAYOUT_JSON_PATH, 'r') as f:
        layout = json.load(f)
except:
    layout = {}



def safe_filename(name):
    name = os.path.splitext(name)[0]
    name = re.sub(r'[^\w\-_.]', '_', name)
    return name

@app.route("/")
def launcher():
    return render_template("launcher.html")

@app.route("/download-guide")
def download_guide():
    return send_from_directory(
        directory=os.path.join(app.static_folder),
        path="user_guide.pdf",
        as_attachment=True
        
    )



@app.route("/layout")
def layout_editor():
    fields = []
    if os.path.exists("layout.json"):
        with open("layout.json", "r") as file:
            layout = json.load(file)
            for f in layout.get("fields", []):
                soup = BeautifulSoup(f.get("label", ""), "html.parser")
                label = soup.get_text()
                fields.append((label, f["x"], f["y"], f["w"], f["h"]))
    return render_template("layout.html", fields=fields)

# 🔹 Background Remover Page
@app.route("/clean")
def clean_ui():
    return render_template("clean.html")
@app.route("/camera")
def camera():
    return render_template("camera.html")




@app.route("/save-photo", methods=["POST"])
def save_photo():
    data = request.json.get("image")
    if not data:
        return jsonify({"error": "No image data"}), 400

    # Decode image
    header, encoded = data.split(",", 1)
    img_data = base64.b64decode(encoded)
    image = Image.open(BytesIO(img_data))

    # Find next index
    existing_files = sorted([
        f for f in os.listdir(CAPTURE_FOLDER) if f.endswith(".jpg")
    ])
    next_index = len(existing_files) + 1
    filename = f"{next_index}.jpg"
    path = os.path.join(CAPTURE_FOLDER, filename)

    # Save image
    image.save(path, "JPEG")
    return jsonify({"filename": f"captured/{filename}"}), 200

# Delete photo route
@app.route("/delete-photo")
def delete_photo():
    filename = request.args.get("filename")
    if not filename:
        return "Missing filename", 400

    path = os.path.join(CAPTURE_FOLDER, os.path.basename(filename))
    if os.path.exists(path):
        os.remove(path)
    return "Deleted", 200

# Download all as ZIP
@app.route("/download-photos")
def download_photos():
    # Remove old ZIP if exists
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    # Rename files in temp folder starting from 1.jpg
    temp_dir = os.path.join(base_dir, 'temp_rename')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    images = sorted([
        f for f in os.listdir(CAPTURE_FOLDER) if f.endswith(".jpg")
    ])

    for i, img_name in enumerate(images, start=1):
        src = os.path.join(CAPTURE_FOLDER, img_name)
        dst = os.path.join(temp_dir, f"{i}.jpg")
        shutil.copy2(src, dst)

    # Create ZIP
    with zipfile.ZipFile(ZIP_PATH, "w") as zipf:
        for fname in sorted(os.listdir(temp_dir), key=lambda x: int(x.split(".")[0])):
            fpath = os.path.join(temp_dir, fname)
            zipf.write(fpath, fname)

    shutil.rmtree(temp_dir)
    return send_file(ZIP_PATH, as_attachment=True)

# Serve captured images
@app.route('/captured/<filename>')
def captured_file(filename):
    return send_from_directory(CAPTURE_FOLDER, filename)


@app.route("/process", methods=["POST"])
def process():
    # Delete all old files before processing
    for old_file in os.listdir(CLEANED_FOLDER):
        if old_file.endswith(".jpg") or old_file.endswith(".png"):
            try:
                os.remove(os.path.join(CLEANED_FOLDER, old_file))
                print(f"🗑 Deleted old file: {old_file}")
            except Exception as e:
                print(f"❌ Could not delete old file: {e}")

    processed = []
    for file in request.files.getlist("photos"):
        safe_name = safe_filename(file.filename)
        fname = f"{safe_name}.png"

        img_data = remove(file.read())
        img = Image.open(BytesIO(img_data)).convert("RGBA")

        save_path = os.path.join(CLEANED_FOLDER, fname)
        img.save(save_path, format="PNG")

        processed.append(fname)

    return jsonify({"processed": processed})



# --- Background Remover /recolor
@app.route("/recolor", methods=["POST"])
def recolor():
    fname = request.form["filename"]
    hex_color = request.form["color"].lstrip("#")
    color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    size = (600, 800)

    transparent_path = os.path.join("static/cleaned", fname)
    img = Image.open(transparent_path).convert("RGBA")

    bg_img = Image.new("RGBA", size, color + (255,))
    
    # सीधे original image को size में fit करें, crop न करें
    final_img = ImageOps.contain(img, size, method=Image.LANCZOS)

    # सीधे background पर फिक्स करें
    offset_x = (size[0] - final_img.width) // 2
    offset_y = (size[1] - final_img.height) // 2
    bg_img.paste(final_img, (offset_x, offset_y), final_img)

    jpg_name = fname.replace(".png", ".jpg")
    jpg_path = os.path.join("static/cleaned", jpg_name)
    bg_img.convert("RGB").save(jpg_path, format="JPEG", quality=95)
    return jsonify({"updated": jpg_name})

def clean_old_files():
    """Deletes all old files before processing new ones."""
    for fname in os.listdir(CLEANED_FOLDER):
        path = os.path.join(CLEANED_FOLDER, fname)
        try:
            os.remove(path)
            print(f"🗑 Deleted old file: {path}")
        except Exception as e:
            print(f"❌ Error deleting {path}: {e}")


@app.route("/download/<filename>")
def download_one(filename):
    jpg_path = os.path.join(CLEANED_FOLDER, filename)

    if not os.path.exists(jpg_path):
        return "File not found", 404

    with open(jpg_path, "rb") as f:
        data = f.read()

    response = send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=filename,
        mimetype="image/jpeg"
    )

    # ✅ Delete after sending
    @response.call_on_close
    def cleanup():
        try:
            os.remove(jpg_path)
            print(f"✅ Deleted: {jpg_path}")
        except Exception as e:
            print(f"❌ Could not delete {jpg_path}: {e}")

    return response


@app.route("/download-all")
def download_all():
    zip_buffer = BytesIO()
    zip_files = [f for f in os.listdir(CLEANED_FOLDER) if f.endswith(".jpg")]

    if not zip_files:
        return "No files to download", 404

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in zip_files:
            file_path = os.path.join(CLEANED_FOLDER, fname)
            zf.write(file_path, arcname=fname)

    zip_buffer.seek(0)

    response = send_file(
        zip_buffer,
        mimetype="application/zip",
        download_name="cleaned_images.zip",
        as_attachment=True
    )

    # ✅ Delete all files after sending ZIP
    @response.call_on_close
    def cleanup():
        for fname in zip_files:
            path = os.path.join(CLEANED_FOLDER, fname)
            try:
                os.remove(path)
                print(f"✅ Deleted: {path}")
            except Exception as e:
                print(f"❌ Could not delete {path}: {e}")

    return response




def parse_color(color_hex):
    color_hex = color_hex.lstrip("#")
    if len(color_hex) == 6:
        return tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)

def create_gradient_border(size, radius, thickness, color1, color2):
    w, h = size
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
    gradient = Image.new("RGBA", (w, h), color1)
    for y in range(h):
        ratio = y / h
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        ImageDraw.Draw(gradient).line([(0, y), (w, y)], fill=(r, g, b), width=1)
    base.paste(gradient, (0, 0), mask)
    inner = Image.new("L", (w - 2 * thickness, h - 2 * thickness), 0)
    ImageDraw.Draw(inner).rounded_rectangle([(0, 0), (w - 2 * thickness - 1, h - 2 * thickness - 1)],
                                            radius=max(0, radius - thickness), fill=255)
    mask_inner = Image.new("L", (w, h), 0)
    mask_inner.paste(inner, (thickness, thickness))
    final_mask = ImageChops.subtract(mask, mask_inner)
    return Image.composite(base, Image.new("RGBA", (w, h), (0, 0, 0, 0)), final_mask)

def create_zip(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, folder_path)
                zipf.write(filepath, arcname)
    if os.path.exists(zip_path):
        os.remove(zip_path)






if __name__ == "__main__":
    from flask import Flask
    app.run(host="0.0.0.0", port=5000)

