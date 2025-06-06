import os
import json
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import tweepy
from datetime import datetime, timedelta
import hashlib

HISTORY_FILE = "posted_articles.json"
HASHTAG_FILE = "hashtags.json"
ACCOUNT_FILE = "accounts.json"
SUMMARY_FILE = "summaries.json"

def fetch_latest_ai_articles():
    """Firecrawl MCP ile gelişmiş haber çekme - Sadece son 4 makale"""
    try:
        # Önce mevcut yayınlanan makaleleri yükle
        posted_articles = load_json(HISTORY_FILE)
        posted_urls = [article.get('url', '') for article in posted_articles]
        posted_hashes = [article.get('hash', '') for article in posted_articles]
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        html = requests.get("https://techcrunch.com/category/artificial-intelligence/", headers=headers).text
        soup = BeautifulSoup(html, "html.parser")
        article_links = soup.select("a.loop-card__title-link")[:4]  # Sadece son 4 makale
        
        print(f"🔍 TechCrunch AI kategorisinden son {len(article_links)} makale kontrol ediliyor...")
        
        articles_data = []
        for link_tag in article_links:
            title = link_tag.text.strip()
            url = link_tag['href']
            
            # Makale hash'i oluştur (başlık bazlı)
            article_hash = hashlib.md5(title.encode()).hexdigest()
            
            # Tekrar kontrolü - URL ve hash bazlı
            is_already_posted = url in posted_urls or article_hash in posted_hashes
            
            if is_already_posted:
                print(f"✅ Makale zaten paylaşılmış, atlanıyor: {title[:50]}...")
                continue
            
            # Makale içeriğini gelişmiş şekilde çek
            content = fetch_article_content_advanced(url, headers)
            
            if content and len(content) > 100:  # Minimum içerik kontrolü
                articles_data.append({
                    "title": title, 
                    "url": url, 
                    "content": content,
                    "hash": article_hash,
                    "fetch_date": datetime.now().isoformat(),
                    "is_new": True,  # Yeni makale işareti
                    "already_posted": False
                })
                print(f"🆕 Yeni makale bulundu: {title[:50]}...")
            else:
                print(f"⚠️ İçerik yetersiz, atlanıyor: {title[:50]}...")
        
        print(f"📊 Toplam {len(articles_data)} yeni makale bulundu (son 4 makale kontrol edildi)")
        return articles_data
        
    except Exception as e:
        print(f"Haber çekme hatası: {e}")
        return []

def fetch_article_content_advanced(url, headers):
    """Gelişmiş makale içeriği çekme - Firecrawl benzeri"""
    try:
        article_html = requests.get(url, headers=headers, timeout=10).text
        article_soup = BeautifulSoup(article_html, "html.parser")
        
        # Çoklu selector deneme - daha kapsamlı içerik çekme
        content_selectors = [
            "div.article-content p",
            "div.entry-content p", 
            "div.post-content p",
            "article p",
            "div.content p",
            ".article-body p"
        ]
        
        content = ""
        for selector in content_selectors:
            paragraphs = article_soup.select(selector)
            if paragraphs:
                content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                if len(content) > 200:  # Yeterli içerik bulundu
                    break
        
        # Eğer hala içerik bulunamadıysa, tüm p etiketlerini dene
        if not content:
            all_paragraphs = article_soup.find_all('p')
            content = "\n".join([p.text.strip() for p in all_paragraphs if len(p.text.strip()) > 50])
        
        return content[:2000]  # İçeriği sınırla
        
    except Exception as e:
        print(f"Makale içeriği çekme hatası ({url}): {e}")
        return ""

def load_json(path):
    return json.load(open(path, 'r', encoding='utf-8')) if os.path.exists(path) else []

def save_json(path, data):
    with open(path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def summarize_article(article_content, api_key):
    """LLM ile gelişmiş makale özetleme"""
    prompt = f"""Aşağıdaki AI/teknoloji haberini Türkçe olarak özetle. Özet tweet formatında, ilgi çekici ve bilgilendirici olsun:

Haber İçeriği:
{article_content[:1500]}

Lütfen:
- Maksimum 200 karakter
- Ana konuyu vurgula
- Teknik detayları basitleştir
- İlgi çekici bir dil kullan

Özet:"""
    return openrouter_call(prompt, api_key, max_tokens=100)

def score_article(article_content, api_key):
    prompt = f"""Bu AI/teknoloji haberinin önemini 1-10 arasında değerlendir (sadece sayı):

{article_content[:800]}

Değerlendirme kriterleri:
- Yenilik derecesi
- Sektörel etki
- Geliştiriciler için önem
- Genel ilgi

Puan:"""
    result = openrouter_call(prompt, api_key, max_tokens=5)
    try:
        return int(result.strip().split()[0])
    except:
        return 5

def categorize_article(article_content, api_key):
    prompt = f"""Bu haberin hedef kitlesini belirle:

{article_content[:500]}

Seçenekler: Developer, Investor, General
Cevap:"""
    return openrouter_call(prompt, api_key, max_tokens=10).strip()

def openrouter_call(prompt, api_key, max_tokens=100):
    if not api_key:
        print("API anahtarı bulunamadı")
        return "API anahtarı eksik"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourdomain.com",
        "X-Title": "VibeAI",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",  # Daha güvenilir model
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }
    
    try:
        print(f"[DEBUG] API çağrısı yapılıyor... Model: {payload['model']}")
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        
        print(f"[DEBUG] API Yanıt Kodu: {r.status_code}")
        
        if r.status_code != 200:
            print(f"API Hatası: Durum Kodu {r.status_code}, Yanıt: {r.text}")
            return "API hatası"

        response_json = r.json()
        print(f"[DEBUG] API Yanıtı alındı: {len(str(response_json))} karakter")
        
        if "choices" not in response_json or not response_json["choices"]:
            print(f"API Yanıtında 'choices' anahtarı bulunamadı. Yanıt: {response_json}")
            return "Yanıt formatı hatalı"
        
        content = response_json["choices"][0]["message"]["content"]
        print(f"[DEBUG] İçerik alındı: {len(content)} karakter")
        return content.strip()
        
    except Exception as e:
        print(f"OpenRouter API çağrı hatası: {e}")
        return "Bağlantı hatası"

def generate_ai_tweet_with_content(article_data, api_key):
    """Makale içeriğini okuyarak gelişmiş tweet oluşturma - Karakter limiti kontrolü ile"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    url = article_data.get("url", "")
    
    # Twitter karakter limiti (URL için 23 karakter ayrılır)
    TWITTER_LIMIT = 280
    URL_LENGTH = 25  # "\n\n🔗 " + URL kısaltması için
    MAX_CONTENT_LENGTH = TWITTER_LIMIT - URL_LENGTH
    
    # İngilizce tweet için prompt
    prompt = f"""Create an engaging English tweet about this AI/tech news article. 

Article Title: {title}
Article Content: {content[:1000]}

Requirements:
- Write in English only
- Maximum {MAX_CONTENT_LENGTH} characters (excluding URL)
- Include relevant emojis
- Make it engaging and informative
- Focus on the key innovation or impact
- Use hashtags like #AI #Tech #Innovation
- Do NOT include the URL in the character count

Tweet (max {MAX_CONTENT_LENGTH} chars):"""

    try:
        tweet_text = openrouter_call(prompt, api_key, max_tokens=150)
        
        if tweet_text and len(tweet_text.strip()) > 10:
            # Karakter limiti kontrolü
            if len(tweet_text.strip()) > MAX_CONTENT_LENGTH:
                tweet_text = tweet_text.strip()[:MAX_CONTENT_LENGTH-3] + "..."
            
            # URL'yi ekle
            final_tweet = f"{tweet_text.strip()}\n\n🔗 {url}"
            
            # Final karakter kontrolü
            if len(final_tweet) > TWITTER_LIMIT:
                # Tekrar kısalt
                available_chars = TWITTER_LIMIT - URL_LENGTH - 3  # "..." için
                tweet_text = tweet_text.strip()[:available_chars] + "..."
                final_tweet = f"{tweet_text}\n\n🔗 {url}"
            
            print(f"[DEBUG] Tweet oluşturuldu: {len(final_tweet)} karakter (limit: {TWITTER_LIMIT})")
            
            return final_tweet
        else:
            print("[FALLBACK] API yanıtı yetersiz, fallback tweet oluşturuluyor...")
            return create_fallback_tweet(title, content, url)
            
    except Exception as e:
        print(f"Tweet oluşturma hatası: {e}")
        print("[FALLBACK] API hatası, fallback tweet oluşturuluyor...")
        return create_fallback_tweet(title, content, url)

def create_fallback_tweet(title, content, url=""):
    """API hatası durumunda fallback tweet oluştur - Karakter limiti kontrolü ile"""
    try:
        # Twitter karakter limiti
        TWITTER_LIMIT = 280
        URL_LENGTH = 25  # "\n\n🔗 " + URL için
        MAX_CONTENT_LENGTH = TWITTER_LIMIT - URL_LENGTH
        
        # Başlığı temizle
        clean_title = title.strip()
        
        # İçerikten anahtar kelimeler ve önemli bilgiler çıkar
        content_lower = content.lower()
        title_lower = title.lower()
        combined_text = f"{title_lower} {content_lower}"
        
        # Emoji seç (konuya göre)
        if "funding" in combined_text or "investment" in combined_text or "billion" in combined_text:
            emoji = "💰"
        elif "launch" in combined_text or "release" in combined_text or "unveil" in combined_text:
            emoji = "🚀"
        elif "model" in combined_text or "AI" in combined_text:
            emoji = "🤖"
        elif "research" in combined_text or "development" in combined_text:
            emoji = "🔬"
        elif "security" in combined_text or "government" in combined_text:
            emoji = "🔒"
        elif "acquisition" in combined_text or "acqui-hire" in combined_text:
            emoji = "🤝"
        elif "queries" in combined_text or "search" in combined_text:
            emoji = "🔍"
        else:
            import random
            emojis = ["🤖", "💻", "🚀", "⚡", "🔥", "💡", "🌟", "📱", "🎯", "💰"]
            emoji = random.choice(emojis)
        
        # Sayısal bilgileri çıkar
        import re
        numbers = re.findall(r'\$?(\d+(?:\.\d+)?)\s*(billion|million|%|percent)', combined_text, re.IGNORECASE)
        
        # Şirket isimlerini tespit et
        companies = []
        company_names = ["OpenAI", "Google", "Microsoft", "Meta", "Apple", "Amazon", "Tesla", "Nvidia", "Anthropic", "Perplexity", "Cursor", "DeviantArt", "AMD", "Intel"]
        for company in company_names:
            if company.lower() in combined_text:
                companies.append(company)
        
        # Hashtag'ler oluştur
        hashtags = []
        if "AI" in combined_text or "artificial intelligence" in combined_text:
            hashtags.append("#AI")
        if "tech" in combined_text or "technology" in combined_text:
            hashtags.append("#Tech")
        if "funding" in combined_text or "investment" in combined_text:
            hashtags.append("#Investment")
        
        # Varsayılan hashtag'ler
        if not hashtags:
            hashtags = ["#AI", "#Tech"]
        
        # Innovation ekle
        if "#Innovation" not in hashtags:
            hashtags.append("#Innovation")
        
        # Maksimum 3 hashtag
        hashtags = hashtags[:3]
        hashtag_text = " ".join(hashtags)
        
        # Tweet içeriği oluştur (karakter limiti göz önünde bulundurarak)
        # Hashtag'ler için yer ayır
        hashtag_length = len(hashtag_text)
        available_chars = MAX_CONTENT_LENGTH - hashtag_length - 1  # 1 boşluk için
        
        # Ana tweet metni oluştur
        tweet_parts = []
        
        # Emoji ile başla
        tweet_parts.append(emoji)
        
        # Başlığı ekle (kısaltılmış)
        title_chars = available_chars - 20  # Ek bilgiler için yer bırak
        if len(clean_title) > title_chars:
            clean_title = clean_title[:title_chars-3] + "..."
        tweet_parts.append(clean_title)
        
        # Şirket bilgisi ekle
        if companies:
            main_company = companies[0]
            if "acquisition" in combined_text:
                tweet_parts.append(f"{main_company} makes strategic acquisition")
            elif "funding" in combined_text:
                tweet_parts.append(f"{main_company} secures funding")
            elif "launch" in combined_text:
                tweet_parts.append(f"{main_company} launches innovation")
            else:
                tweet_parts.append(f"{main_company} announces breakthrough")
        
        # Sayısal bilgi ekle
        if numbers:
            largest_num = max(numbers, key=lambda x: float(x[0]))
            if largest_num[1].lower() in ['billion']:
                tweet_parts.append(f"${largest_num[0]}B impact")
            elif largest_num[1].lower() in ['million']:
                tweet_parts.append(f"{largest_num[0]}M milestone")
        
        # Tweet'i birleştir
        main_text = " ".join(tweet_parts)
        
        # Karakter limiti kontrolü
        if len(main_text) + hashtag_length + 1 > MAX_CONTENT_LENGTH:
            # Çok uzunsa kısalt
            available_for_main = MAX_CONTENT_LENGTH - hashtag_length - 1
            main_text = main_text[:available_for_main-3] + "..."
        
        # Final tweet oluştur
        tweet_without_url = f"{main_text} {hashtag_text}"
        
        # URL ekle
        if url:
            fallback_tweet = f"{tweet_without_url}\n\n🔗 {url}"
        else:
            fallback_tweet = tweet_without_url
        
        # Final karakter kontrolü
        if len(fallback_tweet) > TWITTER_LIMIT:
            # Tekrar kısalt
            excess = len(fallback_tweet) - TWITTER_LIMIT
            main_text = main_text[:-(excess + 3)] + "..."
            tweet_without_url = f"{main_text} {hashtag_text}"
            fallback_tweet = f"{tweet_without_url}\n\n🔗 {url}" if url else tweet_without_url
        
        print(f"[FALLBACK] Tweet oluşturuldu: {len(fallback_tweet)} karakter (limit: {TWITTER_LIMIT})")
        
        return fallback_tweet
        
    except Exception as e:
        print(f"Fallback tweet oluşturma hatası: {e}")
        # En basit fallback
        simple_text = f"🤖 {title[:200]}... #AI #Tech #Innovation"
        if url:
            simple_tweet = f"{simple_text}\n\n🔗 {url}"
        else:
            simple_tweet = simple_text
        
        # Karakter limiti kontrolü
        if len(simple_tweet) > TWITTER_LIMIT:
            available = TWITTER_LIMIT - len("\n\n🔗 ") - len(url) - len(" #AI #Tech #Innovation") - 3
            simple_text = f"🤖 {title[:available]}... #AI #Tech #Innovation"
            simple_tweet = f"{simple_text}\n\n🔗 {url}" if url else simple_text
        
        return simple_tweet

def setup_twitter_api():
    """X (Twitter) API kurulumu"""
    try:
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        
        if not all([bearer_token, api_key, api_secret, access_token, access_token_secret]):
            raise ValueError("Twitter API anahtarları eksik. .env dosyasını kontrol edin.")
        
        # Twitter API v2 client
        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True
        )
        
        return client
    except Exception as e:
        print(f"Twitter API kurulum hatası: {e}")
        return None

def post_tweet(tweet_text, article_title=""):
    """X platformunda tweet paylaşma ve Telegram bildirimi"""
    try:
        client = setup_twitter_api()
        if not client:
            return {"success": False, "error": "Twitter API kurulumu başarısız"}
        
        # Tweet uzunluk kontrolü (280 karakter limiti)
        TWITTER_LIMIT = 280
        if len(tweet_text) > TWITTER_LIMIT:
            print(f"[WARNING] Tweet çok uzun ({len(tweet_text)} karakter), kısaltılıyor...")
            
            # URL'yi koruyarak kısalt
            if "\n\n🔗" in tweet_text:
                parts = tweet_text.split("\n\n🔗")
                main_text = parts[0]
                url_part = f"\n\n🔗{parts[1]}"
                
                # Ana metni kısalt
                available_chars = TWITTER_LIMIT - len(url_part)
                if len(main_text) > available_chars:
                    main_text = main_text[:available_chars-3] + "..."
                
                tweet_text = f"{main_text}{url_part}"
            else:
                # URL yoksa direkt kısalt
                tweet_text = tweet_text[:TWITTER_LIMIT-3] + "..."
        
        print(f"[DEBUG] Final tweet uzunluğu: {len(tweet_text)} karakter")
        
        response = client.create_tweet(text=tweet_text)
        
        if response.data:
            tweet_id = response.data['id']
            tweet_url = f"https://twitter.com/user/status/{tweet_id}"
            
            # Telegram bildirimi gönder
            try:
                telegram_result = send_telegram_notification(
                    message=tweet_text,
                    tweet_url=tweet_url,
                    article_title=article_title
                )
                
                if telegram_result.get("success"):
                    print(f"[SUCCESS] Telegram bildirimi gönderildi")
                else:
                    print(f"[WARNING] Telegram bildirimi gönderilemedi: {telegram_result.get('reason', 'unknown')}")
                    
            except Exception as telegram_error:
                print(f"[ERROR] Telegram bildirim hatası: {telegram_error}")
            
            return {
                "success": True, 
                "tweet_id": tweet_id,
                "url": tweet_url,
                "telegram_sent": telegram_result.get("success", False) if 'telegram_result' in locals() else False
            }
        else:
            return {"success": False, "error": "Tweet oluşturulamadı"}
            
    except Exception as e:
        return {"success": False, "error": f"Tweet paylaşım hatası: {str(e)}"}

def mark_article_as_posted(article_data, tweet_result):
    """Makaleyi paylaşıldı olarak işaretle"""
    try:
        posted_articles = load_json(HISTORY_FILE)
        
        posted_article = {
            "title": article_data.get("title", ""),
            "url": article_data.get("url", ""),
            "hash": article_data.get("hash", ""),
            "posted_date": datetime.now().isoformat(),
            "tweet_id": tweet_result.get("tweet_id", ""),
            "tweet_url": tweet_result.get("url", "")
        }
        
        posted_articles.append(posted_article)
        save_json(HISTORY_FILE, posted_articles)
        
        return True
    except Exception as e:
        print(f"Makale kaydetme hatası: {e}")
        return False

def check_duplicate_articles():
    """Tekrarlanan makaleleri temizle"""
    try:
        posted_articles = load_json(HISTORY_FILE)
        
        # Son 30 günlük makaleleri tut
        cutoff_date = datetime.now() - timedelta(days=30)
        
        filtered_articles = []
        seen_hashes = set()
        
        for article in posted_articles:
            try:
                posted_date = datetime.fromisoformat(article.get("posted_date", ""))
                article_hash = article.get("hash", "")
                
                if posted_date > cutoff_date and article_hash not in seen_hashes:
                    filtered_articles.append(article)
                    seen_hashes.add(article_hash)
            except:
                continue
        
        save_json(HISTORY_FILE, filtered_articles)
        return len(posted_articles) - len(filtered_articles)
        
    except Exception as e:
        print(f"Tekrar temizleme hatası: {e}")
        return 0

def generate_ai_digest(summaries_with_links, api_key):
    """Eski fonksiyon - geriye dönük uyumluluk için"""
    if not summaries_with_links:
        return "Özet bulunamadı"
    
    # İlk makaleyi kullanarak tweet oluştur
    first_summary = summaries_with_links[0]
    article_data = {
        "title": "AI Digest",
        "content": first_summary.get("summary", ""),
        "url": first_summary.get("url", "")
    }
    
    return generate_ai_tweet_with_content(article_data, api_key)

def create_pdf(summaries, filename="daily_digest.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="AI Tweet Digest", ln=True, align='C')
    for s in summaries:
        pdf.multi_cell(0, 10, f"• {s}")
    pdf.output(filename)
    return filename

def get_posted_articles_summary():
    """Paylaşılmış makalelerin özetini döndür"""
    try:
        posted_articles = load_json(HISTORY_FILE)
        
        # Son 7 günlük makaleleri al
        cutoff_date = datetime.now() - timedelta(days=7)
        recent_articles = []
        
        for article in posted_articles:
            try:
                posted_date = datetime.fromisoformat(article.get("posted_date", ""))
                if posted_date > cutoff_date:
                    recent_articles.append(article)
            except:
                continue
        
        return {
            "total_posted": len(posted_articles),
            "recent_posted": len(recent_articles),
            "recent_articles": recent_articles[-5:]  # Son 5 makale
        }
        
    except Exception as e:
        print(f"Paylaşılmış makale özeti hatası: {e}")
        return {"total_posted": 0, "recent_posted": 0, "recent_articles": []}

def reset_all_data():
    """Tüm uygulama verilerini sıfırla"""
    try:
        files_to_reset = [
            "posted_articles.json",
            "pending_tweets.json", 
            "summaries.json",
            "hashtags.json",
            "accounts.json"
        ]
        
        reset_count = 0
        for file_path in files_to_reset:
            if os.path.exists(file_path):
                save_json(file_path, [])
                reset_count += 1
                print(f"✅ {file_path} sıfırlandı")
            else:
                # Dosya yoksa boş oluştur
                save_json(file_path, [])
                print(f"🆕 {file_path} oluşturuldu")
        
        return {
            "success": True,
            "message": f"✅ {reset_count} dosya sıfırlandı",
            "reset_files": files_to_reset
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Sıfırlama hatası: {str(e)}",
            "reset_files": []
        }

def clear_pending_tweets():
    """Sadece bekleyen tweet'leri temizle"""
    try:
        pending_tweets = load_json("pending_tweets.json")
        
        # Sadece posted olanları tut, pending olanları sil
        posted_tweets = [t for t in pending_tweets if t.get("status") == "posted"]
        
        save_json("pending_tweets.json", posted_tweets)
        
        cleared_count = len(pending_tweets) - len(posted_tweets)
        
        return {
            "success": True,
            "message": f"✅ {cleared_count} bekleyen tweet temizlendi",
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Temizleme hatası: {str(e)}",
            "cleared_count": 0
        }

def get_data_statistics():
    """Veri istatistiklerini döndür"""
    try:
        stats = {}
        
        # Paylaşılan makaleler
        posted_articles = load_json("posted_articles.json")
        stats["posted_articles"] = len(posted_articles)
        
        # Bekleyen tweet'ler
        pending_tweets = load_json("pending_tweets.json")
        pending_count = len([t for t in pending_tweets if t.get("status") == "pending"])
        posted_count = len([t for t in pending_tweets if t.get("status") == "posted"])
        stats["pending_tweets"] = pending_count
        stats["posted_tweets_in_pending"] = posted_count
        
        # Özetler
        summaries = load_json("summaries.json")
        stats["summaries"] = len(summaries)
        
        # Hashtag'ler
        hashtags = load_json("hashtags.json")
        stats["hashtags"] = len(hashtags)
        
        # Hesaplar
        accounts = load_json("accounts.json")
        stats["accounts"] = len(accounts)
        
        return stats
        
    except Exception as e:
        print(f"İstatistik hatası: {e}")
        return {
            "posted_articles": 0,
            "pending_tweets": 0,
            "posted_tweets_in_pending": 0,
            "summaries": 0,
            "hashtags": 0,
            "accounts": 0
        }

def load_automation_settings():
    """Otomatikleştirme ayarlarını yükle"""
    try:
        settings_data = load_json("automation_settings.json")
        
        # Eğer liste ise (eski format), boş dict döndür
        if isinstance(settings_data, list):
            settings = {}
        else:
            settings = settings_data
        
        # Varsayılan ayarlar
        default_settings = {
            "auto_mode": False,
            "min_score": 5,
            "check_interval_hours": 3,
            "max_articles_per_run": 10,
            "auto_post_enabled": False,
            "require_manual_approval": True,
            "working_hours_only": False,
            "working_hours_start": "09:00",
            "working_hours_end": "18:00",
            "weekend_enabled": True,
            "rate_limit_delay": 2,
            "last_updated": datetime.now().isoformat()
        }
        
        # Eksik ayarları varsayılanlarla doldur
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
        
        return settings
        
    except Exception as e:
        print(f"Ayarlar yükleme hatası: {e}")
        # Varsayılan ayarları döndür
        return {
            "auto_mode": False,
            "min_score": 5,
            "check_interval_hours": 3,
            "max_articles_per_run": 10,
            "auto_post_enabled": False,
            "require_manual_approval": True,
            "working_hours_only": False,
            "working_hours_start": "09:00",
            "working_hours_end": "18:00",
            "weekend_enabled": True,
            "rate_limit_delay": 2,
            "last_updated": datetime.now().isoformat()
        }

def save_automation_settings(settings):
    """Otomatikleştirme ayarlarını kaydet"""
    try:
        settings["last_updated"] = datetime.now().isoformat()
        save_json("automation_settings.json", settings)
        return {"success": True, "message": "✅ Ayarlar başarıyla kaydedildi"}
    except Exception as e:
        return {"success": False, "message": f"❌ Ayarlar kaydedilemedi: {e}"}

def get_automation_status():
    """Otomatikleştirme durumunu kontrol et"""
    try:
        settings = load_automation_settings()
        
        # Çalışma saatleri kontrolü
        if settings.get("working_hours_only", False):
            from datetime import datetime, time
            now = datetime.now()
            start_time = datetime.strptime(settings.get("working_hours_start", "09:00"), "%H:%M").time()
            end_time = datetime.strptime(settings.get("working_hours_end", "18:00"), "%H:%M").time()
            
            current_time = now.time()
            is_working_hours = start_time <= current_time <= end_time
            
            # Hafta sonu kontrolü
            is_weekend = now.weekday() >= 5  # 5=Cumartesi, 6=Pazar
            weekend_allowed = settings.get("weekend_enabled", True)
            
            if is_weekend and not weekend_allowed:
                return {
                    "active": False,
                    "reason": "Hafta sonu çalışma devre dışı",
                    "settings": settings
                }
            
            if not is_working_hours:
                return {
                    "active": False,
                    "reason": f"Çalışma saatleri dışında ({start_time}-{end_time})",
                    "settings": settings
                }
        
        return {
            "active": settings.get("auto_mode", False),
            "reason": "Aktif" if settings.get("auto_mode", False) else "Manuel mod",
            "settings": settings
        }
        
    except Exception as e:
        return {
            "active": False,
            "reason": f"Hata: {e}",
            "settings": {}
        }

def update_scheduler_settings():
    """Scheduler ayarlarını güncelle (scheduler.py için)"""
    try:
        settings = load_automation_settings()
        
        # Scheduler için ayarlar dosyası oluştur
        scheduler_config = {
            "auto_mode": settings.get("auto_mode", False),
            "min_score": settings.get("min_score", 5),
            "check_interval_hours": settings.get("check_interval_hours", 3),
            "max_articles_per_run": settings.get("max_articles_per_run", 10),
            "auto_post_enabled": settings.get("auto_post_enabled", False),
            "rate_limit_delay": settings.get("rate_limit_delay", 2),
            "last_updated": datetime.now().isoformat()
        }
        
        save_json("scheduler_config.json", scheduler_config)
        return {"success": True, "message": "Scheduler ayarları güncellendi"}
        
    except Exception as e:
        return {"success": False, "message": f"Scheduler ayarları güncellenemedi: {e}"}

def validate_automation_settings(settings):
    """Otomatikleştirme ayarlarını doğrula"""
    errors = []
    
    # Minimum skor kontrolü
    min_score = settings.get("min_score", 5)
    if not isinstance(min_score, int) or min_score < 1 or min_score > 10:
        errors.append("Minimum skor 1-10 arasında olmalı")
    
    # Kontrol aralığı kontrolü
    interval = settings.get("check_interval_hours", 3)
    if not isinstance(interval, (int, float)) or interval < 0.5 or interval > 24:
        errors.append("Kontrol aralığı 0.5-24 saat arasında olmalı")
    
    # Maksimum makale sayısı kontrolü
    max_articles = settings.get("max_articles_per_run", 10)
    if not isinstance(max_articles, int) or max_articles < 1 or max_articles > 50:
        errors.append("Maksimum makale sayısı 1-50 arasında olmalı")
    
    # Çalışma saatleri kontrolü
    try:
        start_time = settings.get("working_hours_start", "09:00")
        end_time = settings.get("working_hours_end", "18:00")
        datetime.strptime(start_time, "%H:%M")
        datetime.strptime(end_time, "%H:%M")
    except ValueError:
        errors.append("Çalışma saatleri HH:MM formatında olmalı")
    
    # Rate limit kontrolü
    rate_delay = settings.get("rate_limit_delay", 2)
    if not isinstance(rate_delay, (int, float)) or rate_delay < 0 or rate_delay > 60:
        errors.append("Rate limit gecikmesi 0-60 saniye arasında olmalı")
    
    return errors

def send_telegram_notification(message, tweet_url="", article_title=""):
    """Telegram bot'a bildirim gönder"""
    try:
        settings = load_automation_settings()
        
        if not settings.get("telegram_notifications", False):
            print("[DEBUG] Telegram bildirimleri kapalı")
            return {"success": False, "reason": "disabled"}
        
        bot_token = settings.get("telegram_bot_token", "").strip()
        chat_id = settings.get("telegram_chat_id", "").strip()
        
        if not bot_token or not chat_id:
            print("[WARNING] Telegram bot token veya chat ID eksik")
            return {"success": False, "reason": "missing_credentials"}
        
        # Telegram mesajını hazırla
        telegram_message = f"🤖 **Yeni Tweet Paylaşıldı!**\n\n"
        
        if article_title:
            telegram_message += f"📰 **Makale:** {article_title}\n\n"
        
        telegram_message += f"💬 **Tweet:** {message}\n\n"
        
        if tweet_url:
            telegram_message += f"🔗 **Link:** {tweet_url}\n\n"
        
        telegram_message += f"⏰ **Zaman:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Telegram API'ye gönder
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": str(chat_id),
            "text": telegram_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"[SUCCESS] Telegram bildirimi gönderildi: {chat_id}")
            return {"success": True, "message_id": response.json().get("result", {}).get("message_id")}
        else:
            print(f"[ERROR] Telegram API hatası: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        print(f"[ERROR] Telegram bildirim hatası: {e}")
        return {"success": False, "error": str(e)}

def test_telegram_connection():
    """Telegram bot bağlantısını test et"""
    try:
        settings = load_automation_settings()
        
        bot_token = settings.get("telegram_bot_token", "").strip()
        chat_id = settings.get("telegram_chat_id", "").strip()
        
        if not bot_token or not chat_id:
            return {"success": False, "error": "Bot token veya chat ID eksik"}
        
        # Bot bilgilerini al
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error": f"Bot token geçersiz: {response.status_code}"}
        
        bot_info = response.json().get("result", {})
        
        # Test mesajı gönder
        test_message = f"🧪 **Test Mesajı**\n\nBot başarıyla bağlandı!\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": str(chat_id),
            "text": test_message,
            "parse_mode": "Markdown"
        }
        
        send_response = requests.post(send_url, json=payload, timeout=10)
        
        if send_response.status_code == 200:
            return {
                "success": True, 
                "bot_name": bot_info.get("first_name", "Unknown"),
                "bot_username": bot_info.get("username", "Unknown")
            }
        else:
            error_detail = send_response.text
            return {"success": False, "error": f"Mesaj gönderilemedi: {send_response.status_code} - {error_detail}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_telegram_chat_id(bot_token):
    """Bot'a mesaj gönderen kullanıcıların chat ID'lerini al"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"success": False, "error": "Bot token geçersiz"}
        
        data = response.json()
        updates = data.get("result", [])
        
        chat_ids = []
        for update in updates[-10:]:  # Son 10 mesaj
            message = update.get("message", {})
            chat = message.get("chat", {})
            if chat.get("id"):
                chat_info = {
                    "chat_id": chat.get("id"),
                    "type": chat.get("type"),
                    "title": chat.get("title") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip()
                }
                if chat_info not in chat_ids:
                    chat_ids.append(chat_info)
        
        return {"success": True, "chat_ids": chat_ids}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
