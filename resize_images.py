#!/usr/bin/env python3
"""Script per ridimensionare le immagini al 50% della loro dimensione originale."""

from PIL import Image
import os
from pathlib import Path

img_dir = Path(__file__).parent / "img"

# Estensioni immagini da elaborare
valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

# Immagini da non processare
skip_files = {'.DS_Store'}

for file in img_dir.iterdir():
    if file.name in skip_files:
        continue
    
    if file.suffix.lower() not in valid_extensions:
        continue
    
    if not file.is_file():
        continue
    
    try:
        print(f"Elaborazione: {file.name}...", end=" ")
        
        # Apri l'immagine
        img = Image.open(file)
        original_size = img.size
        
        # Calcola le nuove dimensioni (50%)
        new_width = int(original_size[0] * 0.5)
        new_height = int(original_size[1] * 0.5)
        
        # Ridimensiona l'immagine con qualità alta
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Salva l'immagine ridimensionata (sovrascrive l'originale)
        img_resized.save(file, optimize=True, quality=95)
        
        print(f"✓ Ridotto da {original_size} a ({new_width}, {new_height})")
        
    except Exception as e:
        print(f"✗ Errore: {e}")

print("\nRidimensionamento completato!")
