import shutil

mapping = {
    r"c:\Users\sawban\Desktop\coc-tools\Screenshot 2026-07-08 160347.png": r"c:\Users\sawban\Desktop\coc-tools\templates\dragon.png",
    r"c:\Users\sawban\Desktop\coc-tools\Screenshot 2026-07-08 160352.png": r"c:\Users\sawban\Desktop\coc-tools\templates\grand_warden.png",
    r"c:\Users\sawban\Desktop\coc-tools\Screenshot 2026-07-08 160358.png": r"c:\Users\sawban\Desktop\coc-tools\templates\stone_slammer.png",
    r"c:\Users\sawban\Desktop\coc-tools\Screenshot 2026-07-08 160403.png": r"c:\Users\sawban\Desktop\coc-tools\templates\rage_spell.png",
    r"c:\Users\sawban\Desktop\coc-tools\Screenshot 2026-07-08 160408.png": r"c:\Users\sawban\Desktop\coc-tools\templates\freeze_spell.png"
}

for src, dst in mapping.items():
    try:
        shutil.copy2(src, dst)
        print(f"Copied {src} to {dst}")
    except Exception as e:
        print(f"Error copying {src}: {e}")
