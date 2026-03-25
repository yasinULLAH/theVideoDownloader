# 🚀 YD — Video Downloader 
### **The Ultimate Open-Source Media Extraction Toolkit**

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-red?style=for-the-badge)](https://github.com/yt-dlp/yt-dlp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

**YD — Video Downloader** is a high-performance, feature-rich GUI application built with Python. It leverages the power of `yt-dlp` to provide a seamless experience for downloading videos and audio from over 1,000+ websites including YouTube, Vimeo, Twitch, and more. 

Designed with a modern "Dark Mode" aesthetic using **CustomTkinter**, YD offers advanced features like batch queuing, SponsorBlock integration, and automatic clipboard monitoring.

---

## ✨ Key Features

*   **📺 High-Resolution Downloads:** Support for 4K, 1080p, 720p, and more.
*   **🎵 Audio Extraction:** Convert videos directly to high-quality MP3 with custom ID3 tags (Artist, Album, Title).
*   **📂 Batch Queue:** Add multiple URLs and download them all at once.
*   **⏩ SponsorBlock Integration:** Automatically skip sponsorships, intros, and ads within videos.
*   **📋 Smart Clipboard Monitor:** Automatically detects and pastes video links when you copy them.
*   **🛠 Advanced Configuration:**
    *   Proxy & User-Agent support for bypassing restrictions.
    *   Cookie file/Browser integration for private/age-restricted content.
    *   Speed limiting to manage bandwidth.
*   **📜 Download History:** Keep track of your last 300 downloads with a one-click re-download feature.
*   **🖼 Metadata & Subtitles:** Embed thumbnails and SRT subtitles directly into your files.

---

## ⚙️ Installation

### 1. Prerequisites
Ensure you have **Python 3.8+** installed. You also need **FFmpeg** for merging video/audio streams and embedding metadata.

*   **FFmpeg:** [Download FFmpeg](https://ffmpeg.org/download.html) (Ensure it's added to your System PATH).

### 2. Clone the Repository
```bash
git clone https://github.com/yourusername/yd-video-downloader.git
cd yd-video-downloader
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
*Note: If you don't have a requirements file, install the core libraries:*
```bash
pip install customtkinter yt-dlp
```

---

## 🚀 Usage

1.  Run the application:
    ```bash
    python main.py
    ```
2.  **Download Tab:** Paste a URL, select your format (MP4/MP3) and quality, then hit **Start**.
3.  **Queue Tab:** Paste a list of URLs to process them in bulk.
4.  **Settings Tab:** Configure your download path, proxy, or browser cookies for restricted videos.

---

## 🛠 Tech Stack

*   **GUI Framework:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (Modern UI elements)
*   **Downloader Engine:** [yt-dlp](https://github.com/yt-dlp/yt-dlp) (The most powerful CLI downloader)
*   **Backend:** Python (Threading, Queues, JSON-based persistence)
*   **Media Processing:** FFmpeg (Required for conversion/merging)

---

## 🔍 SEO Keywords
`YouTube Downloader GUI`, `Python Video Downloader`, `yt-dlp GUI Windows`, `4K Video Downloader Open Source`, `MP3 Extractor Python`, `SponsorBlock Downloader`, `Batch Video Downloader`, `Yasin Ullah YD Downloader`.

---

## 🤝 Contributing
Contributions are welcome! If you have a feature request or found a bug, please open an issue or submit a pull request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

---

## 👨‍💻 Author
**Yasin Ullah**  
*Programming Expert & UI Enthusiast*

---
**Disclaimer:** This tool is for personal use only. Please respect the Terms of Service of the platforms you download from and the copyrights of the content creators.