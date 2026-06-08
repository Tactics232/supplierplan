"""Erzeugt das Tray-Icon (gefüllter Kreis) in Grün (läuft) oder Rot (gestoppt)."""
from PIL import Image, ImageDraw

GREEN = (40, 170, 70)
RED = (200, 50, 50)


def make_icon(running: bool, size: int = 64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = GREEN if running else RED
    margin = size // 8
    d.ellipse([margin, margin, size - margin, size - margin], fill=color)
    return img
