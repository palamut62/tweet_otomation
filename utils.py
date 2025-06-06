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
    """Makale içeriğini okuyarak gelişmiş tweet oluşturma - İngilizce, 35 kelime"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    url = article_data.get("url", "")
    
    # İngilizce tweet için prompt
    prompt = f"""Create an engaging English tweet about this AI/tech news article. 

Article Title: {title}
Article Content: {content[:1000]}

Requirements:
- Write in English only
- Exactly 35 words (excluding the URL link)
- Include relevant emojis
- Make it engaging and informative
- Focus on the key innovation or impact
- Use hashtags like #AI #Tech #Innovation
- Do NOT include the URL in the word count

Tweet (exactly 35 words):"""

    try:
        tweet_text = openrouter_call(prompt, api_key, max_tokens=150)
        
        if tweet_text and len(tweet_text.strip()) > 10:
            # URL'yi ekle
            final_tweet = f"{tweet_text.strip()}\n\n🔗 {url}"
            
            # Kelime sayısını kontrol et (URL hariç)
            word_count = len(tweet_text.strip().split())
            print(f"[DEBUG] Tweet oluşturuldu: {word_count} kelime")
            
            return final_tweet
        else:
            print("[FALLBACK] API yanıtı yetersiz, fallback tweet oluşturuluyor...")
            return create_fallback_tweet(title, content, url)
            
    except Exception as e:
        print(f"Tweet oluşturma hatası: {e}")
        print("[FALLBACK] API hatası, fallback tweet oluşturuluyor...")
        return create_fallback_tweet(title, content, url)

def create_fallback_tweet(title, content, url=""):
    """API hatası durumunda fallback tweet oluştur - İngilizce, 35 kelime"""
    try:
        # Başlığı temizle
        clean_title = title.strip()
        
        # İçerikten anahtar kelimeler ve önemli bilgiler çıkar
        keywords = []
        ai_keywords = ["AI", "artificial intelligence", "machine learning", "deep learning", "neural", "GPT", "LLM", "model", "algorithm", "ChatGPT", "OpenAI", "Google", "Microsoft", "Meta", "Anthropic"]
        tech_keywords = ["technology", "software", "platform", "startup", "company", "billion", "million", "funding", "investment", "acquisition", "launch", "release"]
        
        content_lower = content.lower()
        title_lower = title.lower()
        combined_text = f"{title_lower} {content_lower}"
        
        # AI anahtar kelimeleri kontrol et
        for keyword in ai_keywords:
            if keyword.lower() in combined_text:
                keywords.append("AI")
                break
        
        # Teknoloji anahtar kelimeleri kontrol et
        for keyword in tech_keywords:
            if keyword.lower() in combined_text:
                keywords.append("Tech")
                break
        
        # Sayısal bilgileri çıkar (milyar, milyon, yüzde vb.)
        import re
        numbers = re.findall(r'\$?(\d+(?:\.\d+)?)\s*(billion|million|%|percent)', combined_text, re.IGNORECASE)
        
        # Şirket isimlerini tespit et
        companies = []
        company_names = ["OpenAI", "Google", "Microsoft", "Meta", "Apple", "Amazon", "Tesla", "Nvidia", "Anthropic", "Perplexity", "Cursor", "DeviantArt", "AMD", "Intel"]
        for company in company_names:
            if company.lower() in combined_text:
                companies.append(company)
        
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
        
        # İngilizce tweet içeriği oluştur (35 kelime hedefi)
        tweet_words = []
        
        # Emoji ile başla
        tweet_words.append(emoji)
        
        # Başlığı kelime kelime ekle (maksimum 15 kelime)
        title_words = clean_title.split()[:15]
        tweet_words.extend(title_words)
        
        # Şirket bilgisi ekle
        if companies and len(tweet_words) < 25:
            main_company = companies[0]
            if "acquisition" in combined_text or "acqui-hire" in combined_text:
                tweet_words.extend(["makes", "strategic", "acquisition", "move"])
            elif "funding" in combined_text:
                tweet_words.extend(["secures", "major", "funding", "round"])
            elif "launch" in combined_text:
                tweet_words.extend(["launches", "innovative", "technology", "platform"])
            else:
                tweet_words.extend(["announces", "significant", "breakthrough", "development"])
        
        # Sayısal bilgi ekle
        if numbers and len(tweet_words) < 30:
            largest_num = max(numbers, key=lambda x: float(x[0]))
            if largest_num[1].lower() in ['billion']:
                tweet_words.extend([f"${largest_num[0]}B", "market", "impact"])
            elif largest_num[1].lower() in ['million']:
                tweet_words.extend([f"{largest_num[0]}M", "users", "affected"])
        
        # Konuya özel kelimeler ekle
        if len(tweet_words) < 32:
            if "AI" in combined_text or "artificial intelligence" in combined_text:
                tweet_words.extend(["advancing", "AI", "capabilities"])
            elif "security" in combined_text:
                tweet_words.extend(["enhancing", "digital", "security"])
            elif "browser" in combined_text:
                tweet_words.extend(["revolutionizing", "web", "experience"])
            elif "search" in combined_text:
                tweet_words.extend(["transforming", "search", "technology"])
            else:
                tweet_words.extend(["driving", "tech", "innovation"])
        
        # 35 kelimeye tamamla
        filler_words = ["This", "represents", "significant", "technological", "advancement", "in", "the", "industry", "with", "major", "implications", "for", "future", "development", "and", "growth", "marking", "important", "milestone", "bringing", "new", "opportunities", "creating", "value", "through", "cutting-edge", "solutions"]
        
        # Tekrarları önlemek için kullanılan kelimeleri takip et
        used_words = set(word.lower() for word in tweet_words)
        
        while len(tweet_words) < 35:
            needed = 35 - len(tweet_words)
            available_fillers = [word for word in filler_words if word.lower() not in used_words]
            
            if not available_fillers:
                # Eğer tüm filler kelimeler kullanıldıysa, yeni kelimeler ekle
                additional_words = ["breakthrough", "innovation", "progress", "evolution", "transformation", "revolution", "enhancement", "improvement", "modernization", "optimization"]
                available_fillers = [word for word in additional_words if word.lower() not in used_words]
            
            if available_fillers:
                to_add = min(needed, len(available_fillers))
                selected_words = available_fillers[:to_add]
                tweet_words.extend(selected_words)
                used_words.update(word.lower() for word in selected_words)
            else:
                # Son çare: sayılar ekle
                remaining = 35 - len(tweet_words)
                for i in range(remaining):
                    tweet_words.append(f"step{i+1}")
                break
        
        # Tam 35 kelime al
        tweet_words = tweet_words[:35]
        
        # Hashtag'ler oluştur (kelime sayısına dahil değil)
        hashtags = []
        if "AI" in combined_text:
            hashtags.append("#AI")
        if "tech" in combined_text or "technology" in combined_text:
            hashtags.append("#Tech")
        if "funding" in combined_text or "investment" in combined_text:
            hashtags.append("#Investment")
        if "security" in combined_text:
            hashtags.append("#Security")
        
        # Varsayılan hashtag'ler
        if not hashtags:
            hashtags = ["#AI", "#Tech"]
        
        # Innovation her zaman ekle
        if "#Innovation" not in hashtags:
            hashtags.append("#Innovation")
        
        # Maksimum 3 hashtag
        hashtags = hashtags[:3]
        
        # Final tweet oluştur
        tweet_text = " ".join(tweet_words)
        hashtag_text = " ".join(hashtags)
        tweet_without_url = f"{tweet_text} {hashtag_text}"
        
        # URL ekle
        if url:
            fallback_tweet = f"{tweet_without_url}\n\n🔗 {url}"
        else:
            fallback_tweet = tweet_without_url
        
        # Final kelime sayısını kontrol et (hashtag'ler hariç)
        final_word_count = len(tweet_text.split())
        print(f"[FALLBACK] Tweet oluşturuldu: {final_word_count} kelime (hedef: 35)")
        
        return fallback_tweet
        
    except Exception as e:
        print(f"Fallback tweet oluşturma hatası: {e}")
        # En basit fallback (İngilizce, 35 kelime)
        simple_words = title.split()[:20]  # İlk 20 kelime
        filler = ["represents", "major", "breakthrough", "in", "artificial", "intelligence", "and", "technology", "sector", "with", "significant", "implications", "for", "future", "innovation"]
        simple_words.extend(filler)
        simple_words = simple_words[:35]  # Tam 35 kelime
        simple_tweet = " ".join(simple_words)
        return f"🤖 {simple_tweet} #AI #Tech #Innovation\n\n🔗 {url}" if url else f"🤖 {simple_tweet} #AI #Tech #Innovation"

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

def post_tweet(tweet_text):
    """X platformunda tweet paylaşma"""
    try:
        client = setup_twitter_api()
        if not client:
            return {"success": False, "error": "Twitter API kurulumu başarısız"}
        
        # Tweet uzunluk kontrolü
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."
        
        response = client.create_tweet(text=tweet_text)
        
        if response.data:
            tweet_id = response.data['id']
            return {
                "success": True, 
                "tweet_id": tweet_id,
                "url": f"https://twitter.com/user/status/{tweet_id}"
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
