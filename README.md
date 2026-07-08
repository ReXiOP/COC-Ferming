# Clash of Clans Smart Farming Bot ⚔️

An advanced, AI-powered automation bot for Clash of Clans that utilizes state-of-the-art YOLOv5 object detection and Computer Vision to farm, attack, and execute complex deployment strategies autonomously.

## 🚀 Features

- **Smart Deployment Strategy:** Drop troops, heroes, and spells with pinpoint accuracy.
- **YOLOv5 Integration:** Dynamically detects up to 16 different defensive structures (e.g. Inferno Towers, Eagle Artillery) to prioritize spell deployment in real-time.
- **Automatic Health & Saturation Tracking:** Prevents deploying troops that are already depleted by checking for grayscale visual saturation on the deployment bar.
- **Dynamic Scrolling:** Automatically manages troop bar scrolling to access hidden troops during large army drops.
- **ADB Emulator Control:** Directly hooks into Android emulators via adbutils for non-intrusive background execution.

## 🧠 AI Capabilities

This bot uses a specialized [YOLOv5 Clash of Clans model](https://huggingface.co/keremberke/yolov5s-clash-of-clans) to read the battlefield. Current detectable classes include:
- `ad` (Air Defense), `airsweeper`, `bombtower`, `canon`, `clancastle`
- `eagle` (Eagle Artillery), `inferno` (Inferno Tower)
- `kingpad`, `queenpad`, `wardenpad`, `rcpad`
- `scattershot`, `xbow`, `wizztower`, `mortar`, `th13`

## ⚙️ Configuration

Your deployment strategy is fully customizable via `config.py`. Adjust your target zones, troop counts, and dynamic spell targeting to fit your exact army composition.

```python
DEPLOYMENT_SEQUENCE = [
    # Example Phase: Snipe the Eagle Artillery
    {"name": "freeze_spell", "count": 1, "target": "eagle", "delay": 10}, 
]
```

## 🛠️ Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Connect Emulator:** Ensure your emulator (e.g., LDPlayer) has ADB debugging enabled.
3. **Run the Bot:**
   ```bash
   python main.py
   ```

## 📜 License
This project is for educational and research purposes. Play responsibly.
