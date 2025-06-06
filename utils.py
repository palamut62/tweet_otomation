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
    """Firecrawl MCP ile gelişmiş haber çekme"""
    try:
        # Önce mevcut yayınlanan makaleleri yükle
        posted_articles = load_json(HISTORY_FILE)
        posted_urls = [article.get('url', '') for article in posted_articles]
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        html = requests.get("https://techcrunch.com/category/artificial-intelligence/", headers=headers).text
        soup = BeautifulSoup(html, "html.parser")
        article_links = soup.select("a.loop-card__title-link")[:10]  # Daha fazla makale çek
        
        articles_data = []
        for link_tag in article_links:
            title = link_tag.text.strip()
            url = link_tag['href']
            
            # Tekrar kontrolü - aynı URL'yi tekrar işleme
            if url in posted_urls:
                print(f"Makale zaten işlenmiş, atlanıyor: {title}")
                continue
            
            # Makale hash'i oluştur (başlık bazlı)
            article_hash = hashlib.md5(title.encode()).hexdigest()
            
            # Makale içeriğini gelişmiş şekilde çek
            content = fetch_article_content_advanced(url, headers)
            
            if content and len(content) > 100:  # Minimum içerik kontrolü
                articles_data.append({
                    "title": title, 
                    "url": url, 
                    "content": content,
                    "hash": article_hash,
                    "fetch_date": datetime.now().isoformat()
                })
        
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
        "model": "meta-llama/llama-3.2-3b-instruct:free",  # Daha güvenilir model
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
    """Makale içeriğini okuyarak gelişmiş tweet oluşturma"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    url = article_data.get("url", "")
    
    # Eğer içerik yoksa başlık kullan
    if not content:
        content = title
    
    prompt = f"""Aşağıdaki AI/teknoloji haberinden etkileyici bir tweet oluştur:

Başlık: {title}
İçerik: {content[:1200]}

Tweet Gereksinimleri:
- Maksimum 200 karakter (URL için yer bırak)
- Türkçe olsun
- İlgi çekici emoji kullan
- Relevant hashtag'ler ekle (#AI #Teknoloji #YapayZeka)
- Ana konuyu vurgula
- Merak uyandırıcı olsun
- Sadece tweet metnini döndür, başka açıklama yapma

Tweet:"""
    
    try:
        generated_tweet = openrouter_call(prompt, api_key, max_tokens=150)
        
        # Eğer API çağrısı başarısız olduysa, basit bir tweet oluştur
        if not generated_tweet or generated_tweet == "Özet oluşturulamadı" or len(generated_tweet.strip()) < 10:
            # Fallback tweet oluştur
            generated_tweet = f"🤖 {title[:150]}... #AI #Teknoloji #YapayZeka"
        
        # URL'yi tweet'e ekle
        if url and url != "#":
            # Tweet uzunluğunu kontrol et
            max_tweet_length = 250  # URL için yer bırak
            if len(generated_tweet) > max_tweet_length:
                generated_tweet = generated_tweet[:max_tweet_length-3] + "..."
            
            final_tweet = f"{generated_tweet}\n\n🔗 {url}"
        else:
            final_tweet = generated_tweet
            
        return final_tweet
        
    except Exception as e:
        print(f"Tweet oluşturma hatası: {e}")
        # Hata durumunda basit tweet oluştur
        fallback_tweet = f"🤖 {title[:200]}... #AI #Teknoloji #YapayZeka"
        if url and url != "#":
            fallback_tweet += f"\n\n🔗 {url}"
        return fallback_tweet

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
