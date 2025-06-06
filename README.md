# 🤖 AI Tweet Bot - Gelişmiş Haber Takibi ve Otomatik Tweet Paylaşımı

Bu uygulama, AI/teknoloji haberlerini otomatik olarak takip eder, LLM ile analiz eder ve X (Twitter) platformunda paylaşır.

## ✨ Özellikler

### 🔄 Otomatik Haber Takibi
- TechCrunch AI kategorisinden haberleri çeker
- Firecrawl benzeri gelişmiş içerik çekme
- Tekrarlanan haberleri önleme sistemi
- 3 saatlik periyodik kontrol

### 🤖 AI Destekli Analiz
- LLM ile makale özetleme (Türkçe)
- Haber önem skoru (1-10)
- Hedef kitle kategorilendirme
- İçerik bazlı tweet oluşturma

### 🐦 X (Twitter) Entegrasyonu
- Bearer Token ile tweet paylaşımı
- Otomatik/Manuel mod seçimi
- Tweet uzunluk kontrolü
- Rate limiting koruması

### 📊 Gelişmiş Yönetim
- Streamlit web arayüzü
- Bekleyen tweet'ler sistemi
- Paylaşım geçmişi takibi
- PDF rapor oluşturma

## 🚀 Kurulum

### 1. Gereksinimler
```bash
pip install -r requirements.txt
```

### 2. API Anahtarları
`.env` dosyasında şu anahtarları tanımlayın:

```env
OPENROUTER_API_KEY=your_openrouter_key
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
```

### 3. Twitter API Kurulumu
1. [Twitter Developer Portal](https://developer.twitter.com/) hesabı oluşturun
2. Yeni bir App oluşturun
3. API anahtarlarını alın
4. OAuth 1.0a User Context için gerekli izinleri verin

## 📱 Kullanım

### Web Arayüzü (Streamlit)
```bash
streamlit run streamlit_app.py
```

### Otomatik Zamanlayıcı
```bash
# Otomatik mod (tweet'leri direkt paylaşır)
python scheduler.py --auto

# Manuel mod (onay bekler)
python scheduler.py --manual

# Tek seferlik çalıştırma
python scheduler.py --once
```

## 🎛️ Arayüz Özellikleri

### 📰 Ana Panel
- **Haberleri Yenile**: Yeni haberleri çeker
- **Analiz Et**: Makale skorunu ve kategorisini hesaplar
- **Tweet Oluştur**: AI ile tweet metni oluşturur
- **Tweet Paylaş**: Direkt X'te paylaşır
- **Kaydet**: Manuel onay için bekletir

### ⏳ Bekleyen Tweet'ler
- **Onayla**: Tweet'i paylaşır
- **Reddet**: Tweet'i siler
- **Düzenle**: Tweet metnini değiştirir

### 📊 Sidebar
- Twitter API bağlantı durumu
- Otomatik/Manuel mod seçimi
- Minimum skor ayarı
- İstatistikler

## 🔧 Yapılandırma

### Minimum Skor Ayarı
- 1-10 arası değer
- Düşük skorlu haberler atlanır
- Varsayılan: 6

### Otomatik Mod
- **Açık**: Tweet'ler otomatik paylaşılır
- **Kapalı**: Manuel onay gerekir

### Zamanlama
- Her 3 saatte bir kontrol
- Tekrarlanan makale kontrolü
- 30 günlük geçmiş temizliği

## 📁 Dosya Yapısı

```
ai_tweet_bot_full/
├── app.py                 # Flask ana dosyası
├── streamlit_app.py       # Streamlit web arayüzü
├── utils.py              # Yardımcı fonksiyonlar
├── scheduler.py          # Otomatik zamanlayıcı
├── requirements.txt      # Python gereksinimleri
├── .env                 # API anahtarları
├── posted_articles.json # Paylaşılan makaleler
├── pending_tweets.json  # Bekleyen tweet'ler
├── hashtags.json        # Hashtag'ler
├── accounts.json        # Hesap bilgileri
└── summaries.json       # Özetler
```

## 🛡️ Güvenlik

### API Anahtarları
- `.env` dosyasını asla paylaşmayın
- Git'e `.env` dosyasını eklemeyin
- Düzenli olarak anahtarları yenileyin

### Rate Limiting
- Twitter API limitlerini aşmamak için bekleme süreleri
- OpenRouter API için timeout ayarları
- Hata durumunda graceful handling

## 🔍 Sorun Giderme

### Twitter API Hataları
```bash
# API anahtarlarını kontrol edin
python -c "from utils import setup_twitter_api; print(setup_twitter_api())"
```

### OpenRouter API Hataları
```bash
# API anahtarını test edin
python -c "from utils import openrouter_call; print(openrouter_call('test', 'your_key'))"
```

### Haber Çekme Sorunları
```bash
# Tek makale test edin
python -c "from utils import fetch_latest_ai_articles; print(len(fetch_latest_ai_articles()))"
```

## 📈 İzleme ve Raporlama

### Loglar
- Terminal çıktılarını takip edin
- Hata mesajlarını kontrol edin
- Başarılı işlemleri doğrulayın

### PDF Raporları
- Paylaşılan tweet'lerin özeti
- Tarih bazlı filtreleme
- İndirilebilir format

## 🔄 Güncellemeler

### Yeni Özellikler
- Çoklu haber kaynağı desteği
- Gelişmiş AI modelleri
- Sosyal medya analytics
- Webhook entegrasyonları

### Bakım
- Düzenli dependency güncellemeleri
- Güvenlik yamaları
- Performance optimizasyonları

## 📞 Destek

Sorunlar için:
1. README'yi kontrol edin
2. Log dosyalarını inceleyin
3. API anahtarlarını doğrulayın
4. GitHub Issues kullanın

---

🤖 **AI Tweet Bot** - Otomatik haber takibi ve tweet paylaşımı için gelişmiş çözüm # tweet_otomation
