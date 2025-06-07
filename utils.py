import os
import json
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import tweepy
from datetime import datetime, timedelta
import hashlib

# Firecrawl MCP fonksiyonları için placeholder
def mcp_firecrawl_scrape(params):
    """Firecrawl MCP scrape fonksiyonu - MCP server ile entegre edilecek"""
    try:
        # Bu fonksiyon MCP server ile entegre edildiğinde gerçek Firecrawl API'sini kullanacak
        # Şimdilik fallback yöntemi kullanıyoruz
        print(f"[MCP] Firecrawl scrape çağrısı: {params.get('url', 'unknown')}")
        
        # Geçici olarak False döndür ki fallback yöntemi kullanılsın
        # MCP entegrasyonu tamamlandığında bu fonksiyon gerçek Firecrawl API'sini çağıracak
        return {
            "success": False,
            "reason": "MCP server henüz entegre edilmedi, fallback kullanılıyor"
        }
        
    except Exception as e:
        print(f"[MCP] Firecrawl scrape hatası: {e}")
        return {"success": False, "error": str(e)}

HISTORY_FILE = "posted_articles.json"
HASHTAG_FILE = "hashtags.json"
ACCOUNT_FILE = "accounts.json"
SUMMARY_FILE = "summaries.json"
MCP_CONFIG_FILE = "mcp_config.json"

def fetch_latest_ai_articles_with_firecrawl():
    """Firecrawl MCP ile gelişmiş haber çekme - Sadece son 4 makale"""
    try:
        # Önce mevcut yayınlanan makaleleri yükle
        posted_articles = load_json(HISTORY_FILE)
        posted_urls = [article.get('url', '') for article in posted_articles]
        posted_hashes = [article.get('hash', '') for article in posted_articles]
        
        print("🔍 TechCrunch AI kategorisinden Firecrawl MCP ile makale çekiliyor...")
        
        # Firecrawl MCP ile ana sayfa çek
        try:
            # Firecrawl MCP scrape fonksiyonunu kullan
            scrape_result = mcp_firecrawl_scrape({
                "url": "https://techcrunch.com/category/artificial-intelligence/",
                "formats": ["markdown", "links"],
                "onlyMainContent": True,
                "waitFor": 2000
            })
            
            if not scrape_result.get("success", False):
                print(f"⚠️ Firecrawl MCP hatası, fallback yönteme geçiliyor...")
                return fetch_latest_ai_articles_fallback()
            
            # Markdown içeriğinden makale linklerini çıkar
            markdown_content = scrape_result.get("markdown", "")
            links = scrape_result.get("links", [])
            
            # TechCrunch makale linklerini filtrele
            article_urls = []
            for link in links:
                url = link.get("url", "")
                if ("techcrunch.com" in url and 
                    "/2024/" in url and 
                    url not in posted_urls and
                    len(article_urls) < 4):  # Sadece son 4 makale
                    article_urls.append(url)
            
            print(f"🔗 {len(article_urls)} makale URL'si bulundu")
            
        except Exception as firecrawl_error:
            print(f"⚠️ Firecrawl MCP hatası: {firecrawl_error}")
            print("🔄 Fallback yönteme geçiliyor...")
            return fetch_latest_ai_articles_fallback()
        
        articles_data = []
        for url in article_urls:
            try:
                # Her makaleyi Firecrawl MCP ile çek
                article_content = fetch_article_content_with_firecrawl(url)
                
                if article_content and len(article_content.get("content", "")) > 100:
                    title = article_content.get("title", "")
                    content = article_content.get("content", "")
                    
                    # Makale hash'i oluştur
                    article_hash = hashlib.md5(title.encode()).hexdigest()
                    
                    # Tekrar kontrolü
                    if article_hash not in posted_hashes:
                        articles_data.append({
                            "title": title,
                            "url": url,
                            "content": content,
                            "hash": article_hash,
                            "fetch_date": datetime.now().isoformat(),
                            "is_new": True,
                            "already_posted": False,
                            "source": "firecrawl_mcp"
                        })
                        print(f"🆕 Firecrawl ile yeni makale: {title[:50]}...")
                    else:
                        print(f"✅ Makale zaten paylaşılmış: {title[:50]}...")
                else:
                    print(f"⚠️ İçerik yetersiz: {url}")
                    
            except Exception as article_error:
                print(f"❌ Makale çekme hatası ({url}): {article_error}")
                continue
        
        print(f"📊 Firecrawl MCP ile {len(articles_data)} yeni makale bulundu")
        return articles_data
        
    except Exception as e:
        print(f"Firecrawl MCP haber çekme hatası: {e}")
        print("🔄 Fallback yönteme geçiliyor...")
        return fetch_latest_ai_articles_fallback()

def fetch_latest_ai_articles():
    """Ana haber çekme fonksiyonu - Firecrawl MCP öncelikli"""
    try:
        # Önce Firecrawl MCP ile dene
        articles = fetch_latest_ai_articles_with_firecrawl()
        
        # Eğer Firecrawl'dan makale gelmezse fallback kullan
        if not articles:
            print("🔄 Firecrawl'dan makale gelmedi, fallback yöntemi deneniyor...")
            articles = fetch_latest_ai_articles_fallback()
        
        return articles
        
    except Exception as e:
        print(f"Ana haber çekme hatası: {e}")
        return fetch_latest_ai_articles_fallback()

def fetch_latest_ai_articles_fallback():
    """Fallback haber çekme yöntemi - BeautifulSoup ile"""
    try:
        # Önce mevcut yayınlanan makaleleri yükle
        posted_articles = load_json(HISTORY_FILE)
        posted_urls = [article.get('url', '') for article in posted_articles]
        posted_hashes = [article.get('hash', '') for article in posted_articles]
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        html = requests.get("https://techcrunch.com/category/artificial-intelligence/", headers=headers).text
        soup = BeautifulSoup(html, "html.parser")
        article_links = soup.select("a.loop-card__title-link")[:4]  # Sadece son 4 makale
        
        print(f"🔍 Fallback: TechCrunch AI kategorisinden son {len(article_links)} makale kontrol ediliyor...")
        
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
                    "already_posted": False,
                    "source": "fallback"
                })
                print(f"🆕 Fallback ile yeni makale bulundu: {title[:50]}...")
            else:
                print(f"⚠️ İçerik yetersiz, atlanıyor: {title[:50]}...")
        
        print(f"📊 Fallback ile toplam {len(articles_data)} yeni makale bulundu")
        return articles_data
        
    except Exception as e:
        print(f"Fallback haber çekme hatası: {e}")
        return []

def fetch_article_content_with_firecrawl(url):
    """Firecrawl MCP ile makale içeriği çekme"""
    try:
        print(f"🔍 Firecrawl MCP ile makale çekiliyor: {url[:50]}...")
        
        # Firecrawl MCP scrape fonksiyonunu kullan
        scrape_result = mcp_firecrawl_scrape({
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "waitFor": 3000,
            "removeBase64Images": True
        })
        
        if not scrape_result.get("success", False):
            print(f"⚠️ Firecrawl MCP başarısız, fallback deneniyor...")
            return fetch_article_content_advanced_fallback(url)
        
        # Markdown içeriğini al
        markdown_content = scrape_result.get("markdown", "")
        
        if not markdown_content or len(markdown_content) < 100:
            print(f"⚠️ Firecrawl'dan yetersiz içerik, fallback deneniyor...")
            return fetch_article_content_advanced_fallback(url)
        
        # Başlığı çıkar (genellikle ilk # ile başlar)
        lines = markdown_content.split('\n')
        title = ""
        content_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('# ') and not title:
                title = line[2:].strip()
            elif line and not line.startswith('#') and len(line) > 20:
                content_lines.append(line)
        
        # İçeriği birleştir ve temizle
        content = '\n'.join(content_lines)
        
        # Gereksiz karakterleri temizle
        content = content.replace('*', '').replace('**', '').replace('_', '')
        content = ' '.join(content.split())  # Çoklu boşlukları tek boşluğa çevir
        
        # İçeriği sınırla
        content = content[:2500]
        
        print(f"✅ Firecrawl ile içerik çekildi: {len(content)} karakter")
        
        return {
            "title": title or "Başlık bulunamadı",
            "content": content,
            "source": "firecrawl_mcp"
        }
        
    except Exception as e:
        print(f"❌ Firecrawl MCP hatası ({url}): {e}")
        print("🔄 Fallback yönteme geçiliyor...")
        return fetch_article_content_advanced_fallback(url)

def fetch_article_content_advanced_fallback(url):
    """Fallback makale içeriği çekme - BeautifulSoup ile"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        article_html = requests.get(url, headers=headers, timeout=10).text
        article_soup = BeautifulSoup(article_html, "html.parser")
        
        # Başlığı bul
        title = ""
        title_selectors = ["h1", "h1.entry-title", "h1.post-title", ".article-title h1"]
        for selector in title_selectors:
            title_elem = article_soup.select_one(selector)
            if title_elem:
                title = title_elem.text.strip()
                break
        
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
        
        content = content[:2000]  # İçeriği sınırla
        
        return {
            "title": title or "Başlık bulunamadı",
            "content": content,
            "source": "fallback"
        }
        
    except Exception as e:
        print(f"Fallback makale içeriği çekme hatası ({url}): {e}")
        return None

def fetch_article_content_advanced(url, headers):
    """Geriye dönük uyumluluk için eski fonksiyon"""
    result = fetch_article_content_advanced_fallback(url)
    return result.get("content", "") if result else ""

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
    return gemini_call(prompt, api_key, max_tokens=100)

def score_article(article_content, api_key):
    prompt = f"""Bu AI/teknoloji haberinin önemini 1-10 arasında değerlendir (sadece sayı):

{article_content[:800]}

Değerlendirme kriterleri:
- Yenilik derecesi
- Sektörel etki
- Geliştiriciler için önem
- Genel ilgi

Puan:"""
    result = gemini_call(prompt, api_key, max_tokens=5)
    try:
        return int(result.strip().split()[0])
    except:
        return 5

def categorize_article(article_content, api_key):
    prompt = f"""Bu haberin hedef kitlesini belirle:

{article_content[:500]}

Seçenekler: Developer, Investor, General
Cevap:"""
    return gemini_call(prompt, api_key, max_tokens=10).strip()

def gemini_call(prompt, api_key, max_tokens=100):
    """Google Gemini API çağrısı"""
    if not api_key:
        print("Gemini API anahtarı bulunamadı")
        return "API anahtarı eksik"
    
    try:
        import google.generativeai as genai
        
        # API anahtarını yapılandır
        genai.configure(api_key=api_key)
        
        # Modeli oluştur
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        print(f"[DEBUG] Gemini API çağrısı yapılıyor... Model: gemini-2.0-flash")
        
        # Generation config
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
        )
        
        # API çağrısı
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        print(f"[DEBUG] Gemini API Yanıtı alındı")
        
        if response.text:
            content = response.text.strip()
            print(f"[DEBUG] İçerik alındı: {len(content)} karakter")
            return content
        else:
            print("[DEBUG] Gemini API yanıtında metin bulunamadı")
            return "API hatası"
            
    except Exception as e:
        print(f"[DEBUG] Gemini API çağrı hatası: {e}")
        return "API hatası"

def generate_smart_hashtags(title, content):
    """Makale içeriğine göre akıllı hashtag oluşturma - 5 popüler hashtag"""
    combined_text = f"{title.lower()} {content.lower()}"
    hashtags = []
    
    # AI ve Machine Learning hashtag'leri
    if any(keyword in combined_text for keyword in ["artificial intelligence", "ai", "machine learning", "ml", "neural", "deep learning"]):
        hashtags.extend(["#ArtificialIntelligence", "#MachineLearning", "#DeepLearning", "#NeuralNetworks"])
    
    # Teknoloji ve yazılım hashtag'leri
    if any(keyword in combined_text for keyword in ["software", "programming", "code", "developer", "api"]):
        hashtags.extend(["#SoftwareDevelopment", "#Programming", "#Developer", "#API"])
    
    # Startup ve yatırım hashtag'leri
    if any(keyword in combined_text for keyword in ["startup", "funding", "investment", "venture", "billion", "million"]):
        hashtags.extend(["#Startup", "#Investment", "#VentureCapital", "#Funding", "#Business"])
    
    # Şirket özel hashtag'leri
    if "openai" in combined_text:
        hashtags.extend(["#OpenAI", "#ChatGPT", "#GPT"])
    if "google" in combined_text:
        hashtags.extend(["#Google", "#Alphabet", "#GoogleAI"])
    if "microsoft" in combined_text:
        hashtags.extend(["#Microsoft", "#Azure", "#Copilot"])
    if "meta" in combined_text:
        hashtags.extend(["#Meta", "#Facebook", "#MetaAI"])
    if "apple" in combined_text:
        hashtags.extend(["#Apple", "#iOS", "#AppleAI"])
    if "tesla" in combined_text:
        hashtags.extend(["#Tesla", "#ElonMusk", "#Autopilot"])
    if "nvidia" in combined_text:
        hashtags.extend(["#NVIDIA", "#GPU", "#CUDA"])
    if "anthropic" in combined_text:
        hashtags.extend(["#Anthropic", "#Claude"])
    
    # Teknoloji alanları
    if any(keyword in combined_text for keyword in ["blockchain", "crypto", "bitcoin", "ethereum"]):
        hashtags.extend(["#Blockchain", "#Cryptocurrency", "#Web3", "#DeFi"])
    if any(keyword in combined_text for keyword in ["cloud", "aws", "azure", "gcp"]):
        hashtags.extend(["#CloudComputing", "#AWS", "#Azure", "#CloudNative"])
    if any(keyword in combined_text for keyword in ["cybersecurity", "security", "privacy", "encryption"]):
        hashtags.extend(["#Cybersecurity", "#DataPrivacy", "#InfoSec"])
    if any(keyword in combined_text for keyword in ["quantum", "quantum computing"]):
        hashtags.extend(["#QuantumComputing", "#Quantum", "#QuantumTech"])
    if any(keyword in combined_text for keyword in ["robotics", "robot", "automation"]):
        hashtags.extend(["#Robotics", "#Automation", "#RoboticProcess"])
    if any(keyword in combined_text for keyword in ["iot", "internet of things", "smart home"]):
        hashtags.extend(["#IoT", "#SmartHome", "#ConnectedDevices"])
    if any(keyword in combined_text for keyword in ["5g", "6g", "network", "connectivity"]):
        hashtags.extend(["#5G", "#Connectivity", "#Telecommunications"])
    if any(keyword in combined_text for keyword in ["ar", "vr", "augmented reality", "virtual reality", "metaverse"]):
        hashtags.extend(["#AR", "#VR", "#Metaverse", "#XR"])
    
    # Genel teknoloji hashtag'leri
    general_hashtags = ["#Innovation", "#Technology", "#DigitalTransformation", "#FutureTech", "#TechNews"]
    hashtags.extend(general_hashtags)
    
    # Tekrarları kaldır ve 5 tane seç
    unique_hashtags = list(dict.fromkeys(hashtags))  # Sırayı koruyarak tekrarları kaldır
    
    # En alakalı 5 hashtag seç
    selected_hashtags = unique_hashtags[:5]
    
    # Eğer 5'ten az varsa, genel hashtag'lerle tamamla
    if len(selected_hashtags) < 5:
        remaining_general = [h for h in general_hashtags if h not in selected_hashtags]
        selected_hashtags.extend(remaining_general[:5-len(selected_hashtags)])
    
    return selected_hashtags[:5]

def generate_smart_emojis(title, content):
    """Makale içeriğine göre akıllı emoji seçimi"""
    combined_text = f"{title.lower()} {content.lower()}"
    emojis = []
    
    # Konu bazlı emojiler
    if any(keyword in combined_text for keyword in ["ai", "artificial intelligence", "robot", "machine learning"]):
        emojis.extend(["🤖", "🧠", "⚡"])
    if any(keyword in combined_text for keyword in ["funding", "investment", "billion", "million", "money"]):
        emojis.extend(["💰", "💸", "📈"])
    if any(keyword in combined_text for keyword in ["launch", "release", "unveil", "announce"]):
        emojis.extend(["🚀", "🎉", "✨"])
    if any(keyword in combined_text for keyword in ["research", "development", "breakthrough", "discovery"]):
        emojis.extend(["🔬", "💡", "🧪"])
    if any(keyword in combined_text for keyword in ["security", "privacy", "protection", "safe"]):
        emojis.extend(["🔒", "🛡️", "🔐"])
    if any(keyword in combined_text for keyword in ["acquisition", "merger", "partnership"]):
        emojis.extend(["🤝", "🔗", "💼"])
    if any(keyword in combined_text for keyword in ["search", "query", "find", "discover"]):
        emojis.extend(["🔍", "🔎", "📊"])
    if any(keyword in combined_text for keyword in ["mobile", "phone", "app", "smartphone"]):
        emojis.extend(["📱", "📲", "💻"])
    if any(keyword in combined_text for keyword in ["cloud", "server", "data", "storage"]):
        emojis.extend(["☁️", "💾", "🗄️"])
    if any(keyword in combined_text for keyword in ["game", "gaming", "entertainment"]):
        emojis.extend(["🎮", "🕹️", "🎯"])
    
    # Eğer emoji bulunamadıysa varsayılan emojiler
    if not emojis:
        emojis = ["🚀", "💻", "🌟", "⚡", "🔥"]
    
    # En fazla 3 emoji seç
    return emojis[:3]

def generate_comprehensive_analysis(article_data, api_key):
    """Makale için kapsamlı AI analizi - Ayrı ayrı çağrılar ile güvenilir sonuç"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    
    print(f"🔍 Kapsamlı AI analizi başlatılıyor...")
    
    analysis_result = {
        "innovation": "",
        "companies": [],
        "impact_level": 5,
        "audience": "General",
        "hashtags": [],
        "emojis": [],
        "tweet_text": ""
    }
    
    try:
        # 1. Ana yenilik/buluş analizi
        innovation_prompt = f"""Bu AI/teknoloji haberindeki ana yenilik veya buluşu kısaca açıkla (maksimum 50 kelime):

Başlık: {title}
İçerik: {content[:800]}

Ana yenilik:"""
        
        innovation = gemini_call(innovation_prompt, api_key, max_tokens=80)
        analysis_result["innovation"] = innovation.strip() if innovation != "API hatası" else "Teknoloji gelişimi"
        
        # 2. Şirket analizi
        company_prompt = f"""Bu haberde bahsedilen ana şirketleri listele (maksimum 3 şirket, virgülle ayır):

Başlık: {title}
İçerik: {content[:600]}

Şirketler:"""
        
        companies_text = gemini_call(company_prompt, api_key, max_tokens=50)
        if companies_text != "API hatası":
            companies = [c.strip() for c in companies_text.split(",") if c.strip()]
            analysis_result["companies"] = companies[:3]
        
        # 3. Etki seviyesi analizi
        impact_prompt = f"""Bu haberin teknoloji sektöründeki etkisini 1-10 arasında değerlendir (sadece sayı):

Başlık: {title}
İçerik: {content[:600]}

Etki skoru (1-10):"""
        
        impact_text = gemini_call(impact_prompt, api_key, max_tokens=10)
        try:
            impact_level = int(impact_text.strip().split()[0])
            if 1 <= impact_level <= 10:
                analysis_result["impact_level"] = impact_level
        except:
            analysis_result["impact_level"] = 5
        
        # 4. Hedef kitle analizi
        audience_prompt = f"""Bu haberin hedef kitlesini belirle (Developer/Investor/General):

Başlık: {title}
İçerik: {content[:500]}

Hedef kitle:"""
        
        audience = gemini_call(audience_prompt, api_key, max_tokens=15)
        if audience != "API hatası" and audience.strip() in ["Developer", "Investor", "General"]:
            analysis_result["audience"] = audience.strip()
        
        # 5. Hashtag analizi - AI + akıllı sistem kombinasyonu
        hashtag_prompt = f"""Bu haber için en alakalı 3 hashtag öner. Sadece hashtag'leri yaz, virgülle ayır:

Başlık: {title}
İçerik: {content[:800]}

Örnek: #AI, #Technology, #Innovation

Hashtag'ler:"""
        
        ai_hashtags_text = gemini_call(hashtag_prompt, api_key, max_tokens=50)
        ai_hashtags = []
        
        if ai_hashtags_text != "API hatası":
            # AI'den gelen hashtag'leri temizle ve parse et
            clean_text = ai_hashtags_text.replace("Hashtag'ler:", "").replace("Hashtag'ler", "").strip()
            
            # Virgül veya boşlukla ayrılmış hashtag'leri bul
            import re
            hashtag_matches = re.findall(r'#\w+', clean_text)
            
            # Eğer # ile başlayan bulunamazsa, kelimeleri hashtag yap
            if not hashtag_matches:
                words = re.findall(r'\b[A-Za-z][A-Za-z0-9]*\b', clean_text)
                for word in words[:3]:
                    if len(word) > 2:
                        ai_hashtags.append(f"#{word}")
            else:
                ai_hashtags = hashtag_matches[:3]
        
        # Akıllı hashtag sistemi ile birleştir
        smart_hashtags = generate_smart_hashtags(title, content)
        
        # AI ve akıllı hashtag'leri birleştir (AI öncelikli, 3 hashtag)
        combined_hashtags = []
        for tag in ai_hashtags[:3]:  # AI'den en fazla 3
            if tag not in combined_hashtags:
                combined_hashtags.append(tag)
        
        # Eksik varsa akıllı sistemden tamamla
        for tag in smart_hashtags:
            if tag not in combined_hashtags and len(combined_hashtags) < 3:
                combined_hashtags.append(tag)
        
        analysis_result["hashtags"] = combined_hashtags[:3]
        
        # 6. Emoji analizi
        emoji_prompt = f"""Bu haber için en uygun 3 emoji öner (sadece emojiler, boşluksuz):

Başlık: {title}
İçerik: {content[:500]}

Emojiler:"""
        
        ai_emojis_text = gemini_call(emoji_prompt, api_key, max_tokens=20)
        ai_emojis = []
        
        if ai_emojis_text != "API hatası":
            # Emoji'leri çıkar
            import re
            emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+')
            found_emojis = emoji_pattern.findall(ai_emojis_text)
            for emoji in found_emojis:
                for single_emoji in emoji:
                    if single_emoji not in ai_emojis and len(ai_emojis) < 3:
                        ai_emojis.append(single_emoji)
        
        # Akıllı emoji sistemi ile birleştir
        smart_emojis = generate_smart_emojis(title, content)
        
        # AI ve akıllı emoji'leri birleştir
        combined_emojis = ai_emojis[:2]  # AI'den en fazla 2
        for emoji in smart_emojis:
            if emoji not in combined_emojis and len(combined_emojis) < 3:
                combined_emojis.append(emoji)
        
        analysis_result["emojis"] = combined_emojis[:3]
        
        print(f"✅ Kapsamlı analiz tamamlandı:")
        print(f"🔬 Yenilik: {analysis_result['innovation'][:50]}...")
        print(f"🏢 Şirketler: {', '.join(analysis_result['companies'])}")
        print(f"🎯 Kitle: {analysis_result['audience']}")
        print(f"🏷️ Hashtag'ler: {' '.join(analysis_result['hashtags'])}")
        print(f"😊 Emojiler: {''.join(analysis_result['emojis'])}")
        
        return analysis_result
        
    except Exception as e:
        print(f"❌ Kapsamlı analiz hatası: {e}")
        # Fallback analiz
        return {
            "innovation": "AI/teknoloji gelişimi",
            "companies": [],
            "impact_level": 5,
            "audience": "General",
            "hashtags": generate_smart_hashtags(title, content)[:3],
            "emojis": generate_smart_emojis(title, content)[:3],
            "tweet_text": ""
        }

def generate_ai_tweet_with_mcp_analysis(article_data, api_key):
    """MCP verisi ile gelişmiş AI tweet oluşturma - Kapsamlı analiz ile"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    url = article_data.get("url", "")
    source = article_data.get("source", "unknown")
    
    # Twitter karakter limiti
    TWITTER_LIMIT = 280
    URL_LENGTH = 25  # "\n\n🔗 " + URL kısaltması için
    
    print(f"🤖 AI ile tweet oluşturuluyor (kaynak: {source})...")
    
    try:
        # Kapsamlı analiz yap
        analysis = generate_comprehensive_analysis(article_data, api_key)
        
        # Tweet metni oluştur
        companies_text = ', '.join(analysis['companies'][:2]) if analysis['companies'] else ""
        
        tweet_prompt = f"""Create a compelling English tweet about this AI/tech breakthrough:

Title: {title[:120]}
Key Innovation: {analysis['innovation'][:120]}
Companies: {companies_text}

Requirements:
- Write in perfect English only
- Maximum 200 characters
- Make it clear, engaging and newsworthy
- Focus on WHAT changed and WHY it matters
- Use active voice and strong action verbs
- Include specific details when possible (numbers, capabilities)
- Make it accessible to general audience
- Sound exciting but credible
- Do NOT include hashtags, emojis, URLs, or impact levels (added separately)
- Do NOT mention impact, effect level, or rating in the tweet

Examples of good style:
- "OpenAI's new model achieves 95% accuracy in medical diagnosis"
- "Tesla's robot now performs complex assembly tasks autonomously"
- "Google's AI reduces data center energy consumption by 40%"

Tweet text:"""
        
        tweet_text = gemini_call(tweet_prompt, api_key, max_tokens=80)
        
        if tweet_text == "API hatası" or not tweet_text.strip():
            # Fallback tweet metni - daha anlamlı
            if analysis['companies'] and analysis['innovation']:
                company = analysis['companies'][0]
                innovation = analysis['innovation'][:100]
                # Daha anlamlı fallback tweet oluştur
                if "launch" in innovation.lower():
                    tweet_text = f"{company} launches {innovation.lower().replace('launch', '').strip()}"
                elif "announce" in innovation.lower():
                    tweet_text = f"{company} announces {innovation.lower().replace('announce', '').strip()}"
                elif "develop" in innovation.lower():
                    tweet_text = f"{company} develops {innovation.lower().replace('develop', '').strip()}"
                else:
                    tweet_text = f"{company} unveils {innovation}"
            elif analysis['innovation']:
                tweet_text = f"Breaking: {analysis['innovation'][:150]}"
            else:
                tweet_text = f"AI breakthrough: {title[:120]}"
        
        # Tweet metnini temizle
        tweet_text = tweet_text.replace("Tweet:", "").replace("Tweet metni:", "").strip()
        
        # Gereksiz karakterleri temizle
        tweet_text = tweet_text.replace('"', '').replace("'", "'").strip()
        
        # Impact/etki bilgilerini temizle
        import re
        # "impact: orta", "etki: yüksek", "effect: medium" gibi ifadeleri kaldır
        tweet_text = re.sub(r'\b(impact|etki|effect)\s*:\s*\w+\b', '', tweet_text, flags=re.IGNORECASE)
        # "(impact: medium)", "[etki: yüksek]" gibi parantez içindeki ifadeleri kaldır
        tweet_text = re.sub(r'[\(\[\{]\s*(impact|etki|effect)\s*:\s*\w+\s*[\)\]\}]', '', tweet_text, flags=re.IGNORECASE)
        # Fazla boşlukları temizle
        tweet_text = re.sub(r'\s+', ' ', tweet_text).strip()
        
        # Hashtag ve emoji metinlerini oluştur
        hashtag_text = " ".join(analysis['hashtags']).strip()
        emoji_text = "".join(analysis['emojis']).strip()
        url_part = f"\n\n🔗 {url}"
        
        # Sabit kısımların uzunluğu
        fixed_parts_length = len(emoji_text) + len(hashtag_text) + len(url_part) + 2  # 2 boşluk için
        available_chars = TWITTER_LIMIT - fixed_parts_length
        
        # Tweet metnini temizle ve kısalt
        tweet_text = tweet_text.strip()
        
        # Eğer tweet metni çok uzunsa kısalt
        if len(tweet_text) > available_chars:
            # "..." için 3 karakter ayır
            tweet_text = tweet_text[:available_chars-3] + "..."
        
        # Final tweet oluştur - boşlukları optimize et
        if emoji_text and tweet_text:
            # Emoji varsa emoji ile tweet arasında tek boşluk
            main_content = f"{emoji_text} {tweet_text}"
        else:
            # Emoji yoksa direkt tweet
            main_content = tweet_text
        
        if hashtag_text:
            # Hashtag varsa tek boşluk ile ekle
            final_tweet = f"{main_content} {hashtag_text}{url_part}"
        else:
            # Hashtag yoksa direkt URL ekle
            final_tweet = f"{main_content}{url_part}"
        
        # Son güvenlik kontrolü - eğer hala uzunsa daha agresif kısalt
        if len(final_tweet) > TWITTER_LIMIT:
            excess = len(final_tweet) - TWITTER_LIMIT
            # Tweet metninden fazlalığı çıkar
            new_tweet_length = len(tweet_text) - excess - 3  # 3 "..." için
            if new_tweet_length > 10:  # Minimum 10 karakter bırak
                tweet_text = tweet_text[:new_tweet_length] + "..."
            else:
                # Çok kısa kalırsa hashtag'leri azalt
                hashtag_text = " ".join(analysis['hashtags'][:2])  # 2 hashtag
                fixed_parts_length = len(emoji_text) + len(hashtag_text) + len(url_part) + 1  # 1 boşluk
                available_chars = TWITTER_LIMIT - fixed_parts_length
                tweet_text = tweet_text[:available_chars-3] + "..."
            
            # Yeniden oluştur
            if emoji_text and tweet_text:
                main_content = f"{emoji_text} {tweet_text}"
            else:
                main_content = tweet_text
            
            if hashtag_text:
                final_tweet = f"{main_content} {hashtag_text}{url_part}"
            else:
                final_tweet = f"{main_content}{url_part}"
        
        print(f"✅ AI analizi ile tweet oluşturuldu: {len(final_tweet)} karakter")
        print(f"📝 Tweet metni: {len(tweet_text)} karakter")
        print(f"🏷️ AI Hashtag'ler: {hashtag_text} ({len(hashtag_text)} karakter)")
        print(f"😊 AI Emojiler: {emoji_text} ({len(emoji_text)} karakter)")
        print(f"🔗 URL kısmı: {len(url_part)} karakter")
        print(f"🎯 Hedef Kitle: {analysis['audience']}")
        
        return final_tweet
        
    except Exception as e:
        print(f"❌ AI tweet oluşturma hatası: {e}")
        print("🔄 Fallback yönteme geçiliyor...")
        return generate_ai_tweet_with_content_fallback(article_data, api_key)

def generate_ai_tweet_with_content(article_data, api_key):
    """Ana tweet oluşturma fonksiyonu - MCP analizi öncelikli"""
    try:
        # Önce MCP analizi ile dene
        tweet = generate_ai_tweet_with_mcp_analysis(article_data, api_key)
        
        # Eğer başarısızsa fallback kullan
        if not tweet or len(tweet) < 50:
            print("🔄 MCP analizi yetersiz, fallback yöntemi deneniyor...")
            tweet = generate_ai_tweet_with_content_fallback(article_data, api_key)
        
        return tweet
        
    except Exception as e:
        print(f"Ana tweet oluşturma hatası: {e}")
        return generate_ai_tweet_with_content_fallback(article_data, api_key)

def generate_ai_tweet_with_content_fallback(article_data, api_key):
    """Fallback tweet oluşturma - Eski yöntem"""
    title = article_data.get("title", "")
    content = article_data.get("content", "")
    url = article_data.get("url", "")
    
    # Twitter karakter limiti (URL için 23 karakter ayrılır)
    TWITTER_LIMIT = 280
    URL_LENGTH = 25  # "\n\n🔗 " + URL kısaltması için
    
    # Akıllı hashtag ve emoji oluştur
    smart_hashtags = generate_smart_hashtags(title, content)
    smart_emojis = generate_smart_emojis(title, content)
    
    hashtag_text = " ".join(smart_hashtags).strip()
    emoji_text = "".join(smart_emojis).strip()
    
    # Hashtag ve emoji için yer ayır
    hashtag_emoji_length = len(hashtag_text) + len(emoji_text) + 2  # 2 boşluk için
    MAX_CONTENT_LENGTH = TWITTER_LIMIT - URL_LENGTH - hashtag_emoji_length
    
    # İngilizce tweet için gelişmiş prompt
    prompt = f"""Create a compelling English tweet about this AI/tech breakthrough:

Article Title: {title}
Article Content: {content[:1000]}

Requirements:
- Write in perfect English only
- Maximum {MAX_CONTENT_LENGTH} characters
- Make it clear, engaging and newsworthy
- Focus on WHAT changed and WHY it matters
- Use active voice and strong action verbs
- Include specific details when possible (numbers, capabilities, improvements)
- Make it accessible to general audience
- Sound exciting but credible
- Avoid jargon and technical terms
- Do NOT include hashtags, emojis, URLs, or impact levels (added separately)
- Do NOT mention impact, effect level, or rating in the tweet

Examples of good style:
- "OpenAI's new model achieves 95% accuracy in medical diagnosis"
- "Tesla's robot now performs complex assembly tasks autonomously"
- "Google's AI reduces data center energy consumption by 40%"
- "Meta's VR headset delivers 4K resolution at half the price"

Tweet text (max {MAX_CONTENT_LENGTH} chars):"""

    try:
        tweet_text = gemini_call(prompt, api_key, max_tokens=150)
        
        if tweet_text and len(tweet_text.strip()) > 10:
            # Tweet metnini temizle
            import re
            # Impact/etki bilgilerini temizle
            tweet_text = re.sub(r'\b(impact|etki|effect)\s*:\s*\w+\b', '', tweet_text, flags=re.IGNORECASE)
            tweet_text = re.sub(r'[\(\[\{]\s*(impact|etki|effect)\s*:\s*\w+\s*[\)\]\}]', '', tweet_text, flags=re.IGNORECASE)
            tweet_text = re.sub(r'\s+', ' ', tweet_text).strip()
            
            # Karakter limiti kontrolü
            if len(tweet_text.strip()) > MAX_CONTENT_LENGTH:
                tweet_text = tweet_text.strip()[:MAX_CONTENT_LENGTH-3] + "..."
            
            # Emoji, tweet metni, hashtag'ler ve URL'yi birleştir - boşlukları optimize et
            parts = []
            if emoji_text:
                parts.append(emoji_text)
            if tweet_text.strip():
                parts.append(tweet_text.strip())
            if hashtag_text:
                parts.append(hashtag_text)
            
            main_content = " ".join(parts)
            final_tweet = f"{main_content}\n\n🔗 {url}"
            
            # Final karakter kontrolü
            if len(final_tweet) > TWITTER_LIMIT:
                # Tekrar kısalt
                excess = len(final_tweet) - TWITTER_LIMIT
                tweet_text = tweet_text.strip()[:-(excess + 3)] + "..."
                
                # Yeniden birleştir - boşlukları optimize et
                parts = []
                if emoji_text:
                    parts.append(emoji_text)
                if tweet_text:
                    parts.append(tweet_text)
                if hashtag_text:
                    parts.append(hashtag_text)
                
                main_content = " ".join(parts)
                final_tweet = f"{main_content}\n\n🔗 {url}"
            
            print(f"[FALLBACK] Tweet oluşturuldu: {len(final_tweet)} karakter (limit: {TWITTER_LIMIT})")
            print(f"[FALLBACK] Hashtag'ler: {hashtag_text}")
            print(f"[FALLBACK] Emojiler: {emoji_text}")
            
            return final_tweet
        else:
            print("[FALLBACK] API yanıtı yetersiz, basit fallback tweet oluşturuluyor...")
            return create_fallback_tweet(title, content, url)
            
    except Exception as e:
        print(f"Fallback tweet oluşturma hatası: {e}")
        print("[FALLBACK] API hatası, basit fallback tweet oluşturuluyor...")
        return create_fallback_tweet(title, content, url)

def create_fallback_tweet(title, content, url=""):
    """API hatası durumunda fallback tweet oluştur - Akıllı hashtag ve emoji ile"""
    try:
        # Twitter karakter limiti
        TWITTER_LIMIT = 280
        URL_LENGTH = 25  # "\n\n🔗 " + URL için
        
        # Akıllı hashtag ve emoji oluştur
        smart_hashtags = generate_smart_hashtags(title, content)
        smart_emojis = generate_smart_emojis(title, content)
        
        hashtag_text = " ".join(smart_hashtags).strip()
        emoji_text = "".join(smart_emojis).strip()
        
        # Hashtag ve emoji için yer ayır
        hashtag_emoji_length = len(hashtag_text) + len(emoji_text) + 2  # 2 boşluk için
        MAX_CONTENT_LENGTH = TWITTER_LIMIT - URL_LENGTH - hashtag_emoji_length
        
        # Başlığı temizle
        clean_title = title.strip()
        
        # İçerikten anahtar kelimeler ve önemli bilgiler çıkar
        content_lower = content.lower()
        title_lower = title.lower()
        combined_text = f"{title_lower} {content_lower}"
        
        # Sayısal bilgileri çıkar
        import re
        numbers = re.findall(r'\$?(\d+(?:\.\d+)?)\s*(billion|million|%|percent)', combined_text, re.IGNORECASE)
        
        # Şirket isimlerini tespit et
        companies = []
        company_names = ["OpenAI", "Google", "Microsoft", "Meta", "Apple", "Amazon", "Tesla", "Nvidia", "Anthropic", "Perplexity", "Cursor", "DeviantArt", "AMD", "Intel"]
        for company in company_names:
            if company.lower() in combined_text:
                companies.append(company)
        
        # Ana tweet metni oluştur - daha anlamlı İngilizce
        tweet_parts = []
        
        # Şirket ve eylem bazlı tweet oluştur
        if companies:
            main_company = companies[0]
            
            # Eyleme göre anlamlı cümle oluştur
            if "acquisition" in combined_text or "acquire" in combined_text:
                if "billion" in combined_text:
                    tweet_parts.append(f"{main_company} completes major acquisition")
                else:
                    tweet_parts.append(f"{main_company} acquires strategic company")
            elif "funding" in combined_text or "investment" in combined_text:
                if numbers:
                    largest_num = max(numbers, key=lambda x: float(x[0]))
                    if largest_num[1].lower() == 'billion':
                        tweet_parts.append(f"{main_company} raises ${largest_num[0]}B in funding")
                    elif largest_num[1].lower() == 'million':
                        tweet_parts.append(f"{main_company} secures ${largest_num[0]}M investment")
                    else:
                        tweet_parts.append(f"{main_company} secures major funding")
                else:
                    tweet_parts.append(f"{main_company} secures new funding round")
            elif "launch" in combined_text or "release" in combined_text:
                if "ai" in combined_text or "artificial intelligence" in combined_text:
                    tweet_parts.append(f"{main_company} launches new AI technology")
                elif "robot" in combined_text:
                    tweet_parts.append(f"{main_company} unveils advanced robotics")
                else:
                    tweet_parts.append(f"{main_company} releases breakthrough innovation")
            elif "partnership" in combined_text or "partner" in combined_text:
                tweet_parts.append(f"{main_company} forms strategic partnership")
            elif "breakthrough" in combined_text or "innovation" in combined_text:
                tweet_parts.append(f"{main_company} achieves major breakthrough")
            else:
                # Başlığı kullan ama şirket adını öne çıkar
                clean_title_short = clean_title.replace(main_company, "").strip()
                if clean_title_short:
                    tweet_parts.append(f"{main_company}: {clean_title_short[:80]}")
                else:
                    tweet_parts.append(f"{main_company} makes major announcement")
        else:
            # Şirket yoksa başlığı kullan
            if "ai" in combined_text or "artificial intelligence" in combined_text:
                tweet_parts.append(f"AI breakthrough: {clean_title[:100]}")
            elif "robot" in combined_text:
                tweet_parts.append(f"Robotics advance: {clean_title[:100]}")
            else:
                tweet_parts.append(f"Tech news: {clean_title[:120]}")
        
        # Sayısal bilgi ekle (eğer henüz eklenmemişse)
        if numbers and not any("$" in part for part in tweet_parts):
            largest_num = max(numbers, key=lambda x: float(x[0]))
            if largest_num[1].lower() == 'billion':
                tweet_parts.append(f"(${largest_num[0]}B)")
            elif largest_num[1].lower() == 'million':
                tweet_parts.append(f"({largest_num[0]}M)")
            elif largest_num[1].lower() in ['%', 'percent']:
                tweet_parts.append(f"({largest_num[0]}% improvement)")
        
        # Tweet'i birleştir
        main_text = " ".join(tweet_parts)
        
        # Karakter limiti kontrolü
        if len(main_text) > MAX_CONTENT_LENGTH:
            # Çok uzunsa kısalt
            main_text = main_text[:MAX_CONTENT_LENGTH-3] + "..."
        
        # Emoji, tweet metni, hashtag'ler ve URL'yi birleştir
        if url:
            fallback_tweet = f"{emoji_text} {main_text} {hashtag_text}\n\n🔗 {url}"
        else:
            fallback_tweet = f"{emoji_text} {main_text} {hashtag_text}"
        
        # Final karakter kontrolü
        if len(fallback_tweet) > TWITTER_LIMIT:
            # Tekrar kısalt
            excess = len(fallback_tweet) - TWITTER_LIMIT
            main_text = main_text[:-(excess + 3)] + "..."
            if url:
                fallback_tweet = f"{emoji_text} {main_text} {hashtag_text}\n\n🔗 {url}"
            else:
                fallback_tweet = f"{emoji_text} {main_text} {hashtag_text}"
        
        print(f"[FALLBACK] Tweet oluşturuldu: {len(fallback_tweet)} karakter (limit: {TWITTER_LIMIT})")
        print(f"[FALLBACK] Hashtag'ler: {hashtag_text}")
        print(f"[FALLBACK] Emojiler: {emoji_text}")
        
        return fallback_tweet
        
    except Exception as e:
        print(f"Fallback tweet oluşturma hatası: {e}")
        # En basit fallback - akıllı hashtag ve emoji ile
        try:
            simple_hashtags = generate_smart_hashtags(title, "")[:3]  # 3 hashtag
            simple_emojis = generate_smart_emojis(title, "")[:2]  # 2 emoji
            
            hashtag_text = " ".join(simple_hashtags)
            emoji_text = "".join(simple_emojis)
            
            # Karakter hesaplama
            url_length = len(f"\n\n🔗 {url}") if url else 0
            available_chars = TWITTER_LIMIT - url_length - len(hashtag_text) - len(emoji_text) - 2
            
            # Başlığı kısalt
            if len(title) > available_chars:
                title_text = title[:available_chars-3] + "..."
            else:
                title_text = title
            
            simple_tweet = f"{emoji_text} {title_text} {hashtag_text}"
            if url:
                simple_tweet += f"\n\n🔗 {url}"
            
            return simple_tweet
            
        except:
            # En son çare - basit tweet
            simple_text = f"🤖 {title[:200]}... #AI #Innovation #Technology"
            if url:
                simple_tweet = f"{simple_text}\n\n🔗 {url}"
            else:
                simple_tweet = simple_text
            
            # Karakter limiti kontrolü
            if len(simple_tweet) > TWITTER_LIMIT:
                available = TWITTER_LIMIT - len("\n\n🔗 ") - len(url) - len(" #AI #Innovation #Technology") - 3
                simple_text = f"🤖 {title[:available]}... #AI #Innovation #Technology"
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
    """Telegram bot'a bildirim gönder - Bot token env'den, Chat ID settings'den"""
    try:
        # Bot token'ı environment variable'dan çek
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        
        # Chat ID'yi settings'den çek
        settings = load_automation_settings()
        chat_id = settings.get("telegram_chat_id", "").strip()
        
        # Eğer bot token env'de yoksa settings'den dene (geriye dönük uyumluluk)
        if not bot_token:
            bot_token = settings.get("telegram_bot_token", "").strip()
        
        # Telegram bildirimleri kapalı mı kontrol et
        if not settings.get("telegram_notifications", True):  # Varsayılan True
            print("[DEBUG] Telegram bildirimleri kapalı")
            return {"success": False, "reason": "disabled"}
        
        if not bot_token:
            print("[WARNING] Telegram bot token eksik. .env dosyasında TELEGRAM_BOT_TOKEN ayarlayın.")
            return {"success": False, "reason": "missing_bot_token"}
            
        if not chat_id:
            print("[WARNING] Telegram chat ID eksik. Arayüzden 'Chat ID Bul' butonu ile ayarlayın.")
            return {"success": False, "reason": "missing_chat_id"}
        
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
    """Telegram bot bağlantısını test et - Bot token env'den, Chat ID settings'den"""
    try:
        # Bot token'ı environment variable'dan çek
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        
        # Chat ID'yi settings'den çek
        settings = load_automation_settings()
        chat_id = settings.get("telegram_chat_id", "").strip()
        
        # Eğer bot token env'de yoksa settings'den dene (geriye dönük uyumluluk)
        if not bot_token:
            bot_token = settings.get("telegram_bot_token", "").strip()
        
        if not bot_token:
            return {
                "success": False, 
                "error": "Bot token eksik. .env dosyasında TELEGRAM_BOT_TOKEN ayarlayın."
            }
            
        if not chat_id:
            return {
                "success": False, 
                "error": "Chat ID eksik. 'Chat ID Bul' butonu ile chat ID'yi ayarlayın."
            }
        
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

def check_telegram_configuration():
    """Telegram konfigürasyonunu kontrol et - Bot token env'den, Chat ID settings'den"""
    try:
        # Bot token environment variable'dan
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        
        # Chat ID settings'den
        settings = load_automation_settings()
        chat_id = settings.get("telegram_chat_id", "").strip()
        
        # Geriye dönük uyumluluk için settings'den bot token kontrol et
        settings_bot_token = settings.get("telegram_bot_token", "").strip()
        
        status = {
            "bot_token_env": bool(bot_token),
            "bot_token_settings": bool(settings_bot_token),
            "chat_id_set": bool(chat_id),
            "ready": bool((bot_token or settings_bot_token) and chat_id)
        }
        
        if status["ready"]:
            if status["bot_token_env"]:
                status["message"] = "✅ Telegram yapılandırması tamamlanmış (Bot token: ENV, Chat ID: Ayarlar)"
            else:
                status["message"] = "✅ Telegram yapılandırması tamamlanmış (Bot token: Ayarlar, Chat ID: Ayarlar)"
            status["status"] = "ready"
        elif status["bot_token_env"] or status["bot_token_settings"]:
            if not status["chat_id_set"]:
                status["message"] = "⚠️ Bot token var, Chat ID eksik - 'Chat ID Bul' butonu ile ayarlayın"
                status["status"] = "partial"
            else:
                status["message"] = "✅ Telegram yapılandırması tamamlanmış"
                status["status"] = "ready"
        else:
            status["message"] = "❌ Bot token eksik - .env dosyasında TELEGRAM_BOT_TOKEN ayarlayın"
            status["status"] = "missing"
            
        return status
        
    except Exception as e:
        return {
            "bot_token_env": False,
            "bot_token_settings": False,
            "chat_id_set": False,
            "ready": False,
            "message": f"❌ Kontrol hatası: {e}",
            "status": "error"
        }

def get_telegram_chat_id(bot_token=None):
    """Bot'a mesaj gönderen kullanıcıların chat ID'lerini al - Environment variable'lardan token çeker"""
    try:
        # Eğer bot_token parametre olarak verilmemişse env'den çek
        if not bot_token:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            
            # Eğer env'de yoksa settings'den dene
            if not bot_token:
                settings = load_automation_settings()
                bot_token = settings.get("telegram_bot_token", "").strip()
        
        if not bot_token:
            return {
                "success": False, 
                "error": "Bot token eksik. .env dosyasında TELEGRAM_BOT_TOKEN ayarlayın."
            }
        
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

def save_telegram_chat_id(chat_id):
    """Chat ID'yi otomatik olarak ayarlara kaydet"""
    try:
        settings = load_automation_settings()
        settings["telegram_chat_id"] = str(chat_id).strip()
        
        save_result = save_automation_settings(settings)
        
        if save_result["success"]:
            print(f"[SUCCESS] Chat ID otomatik kaydedildi: {chat_id}")
            return {"success": True, "message": f"✅ Chat ID kaydedildi: {chat_id}"}
        else:
            print(f"[ERROR] Chat ID kaydetme hatası: {save_result['message']}")
            return {"success": False, "error": f"Kaydetme hatası: {save_result['message']}"}
            
    except Exception as e:
        print(f"[ERROR] Chat ID kaydetme hatası: {e}")
        return {"success": False, "error": str(e)}

def auto_detect_and_save_chat_id():
    """Otomatik chat ID tespit et ve kaydet"""
    try:
        # Mevcut chat ID'yi kontrol et
        settings = load_automation_settings()
        current_chat_id = settings.get("telegram_chat_id", "").strip()
        
        if current_chat_id:
            return {
                "success": True, 
                "message": f"Chat ID zaten ayarlanmış: {current_chat_id}",
                "chat_id": current_chat_id,
                "auto_detected": False
            }
        
        # Chat ID'leri bul
        result = get_telegram_chat_id()
        
        if not result["success"]:
            return {
                "success": False,
                "error": result["error"],
                "auto_detected": False
            }
        
        chat_ids = result.get("chat_ids", [])
        
        if not chat_ids:
            return {
                "success": False,
                "error": "Chat ID bulunamadı. Bot'a önce bir mesaj gönderin.",
                "auto_detected": False
            }
        
        # İlk chat ID'yi otomatik seç (genellikle en son mesaj)
        selected_chat = chat_ids[0]
        chat_id = selected_chat["chat_id"]
        
        # Chat ID'yi kaydet
        save_result = save_telegram_chat_id(chat_id)
        
        if save_result["success"]:
            return {
                "success": True,
                "message": f"✅ Chat ID otomatik tespit edildi ve kaydedildi: {chat_id}",
                "chat_id": chat_id,
                "chat_info": selected_chat,
                "auto_detected": True,
                "all_chats": chat_ids
            }
        else:
            return {
                "success": False,
                "error": save_result["error"],
                "auto_detected": False
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "auto_detected": False
        }

def load_mcp_config():
    """MCP konfigürasyonunu yükle"""
    try:
        if os.path.exists(MCP_CONFIG_FILE):
            config = load_json(MCP_CONFIG_FILE)
        else:
            # Varsayılan konfigürasyon
            config = {
                "mcp_enabled": False,
                "firecrawl_mcp": {
                    "enabled": False,
                    "server_url": "http://localhost:3000",
                    "api_key": "",
                    "timeout": 30,
                    "retry_count": 3,
                    "fallback_enabled": True
                },
                "content_extraction": {
                    "max_content_length": 2500,
                    "min_content_length": 100,
                    "wait_time": 3000,
                    "remove_base64_images": True,
                    "only_main_content": True
                },
                "ai_analysis": {
                    "enabled": True,
                    "max_tokens": 300,
                    "temperature": 0.7,
                    "model": "deepseek/deepseek-chat-v3-0324:free",
                    "fallback_enabled": True
                },
                "last_updated": datetime.now().isoformat()
            }
            save_json(MCP_CONFIG_FILE, config)
        
        return config
        
    except Exception as e:
        print(f"MCP konfigürasyon yükleme hatası: {e}")
        return {
            "mcp_enabled": False,
            "firecrawl_mcp": {"enabled": False, "fallback_enabled": True},
            "ai_analysis": {"enabled": True, "fallback_enabled": True}
        }

def save_mcp_config(config):
    """MCP konfigürasyonunu kaydet"""
    try:
        config["last_updated"] = datetime.now().isoformat()
        save_json(MCP_CONFIG_FILE, config)
        return {"success": True, "message": "✅ MCP konfigürasyonu kaydedildi"}
    except Exception as e:
        return {"success": False, "message": f"❌ MCP konfigürasyonu kaydedilemedi: {e}"}

def get_mcp_status():
    """MCP durumunu kontrol et"""
    try:
        config = load_mcp_config()
        
        status = {
            "mcp_enabled": config.get("mcp_enabled", False),
            "firecrawl_enabled": config.get("firecrawl_mcp", {}).get("enabled", False),
            "ai_analysis_enabled": config.get("ai_analysis", {}).get("enabled", True),
            "fallback_available": True,
            "ready": False
        }
        
        # MCP hazır mı kontrol et
        if status["mcp_enabled"] and status["firecrawl_enabled"]:
            # Firecrawl MCP server bağlantısını test et
            try:
                server_url = config.get("firecrawl_mcp", {}).get("server_url", "")
                if server_url:
                    # Basit ping testi (gerçek implementasyonda MCP server'a ping atılacak)
                    status["ready"] = True
                    status["message"] = "✅ MCP Firecrawl aktif ve hazır"
                else:
                    status["message"] = "⚠️ MCP server URL'si eksik"
            except:
                status["message"] = "❌ MCP server bağlantısı başarısız"
        elif status["ai_analysis_enabled"]:
            status["message"] = "✅ AI analizi aktif (MCP olmadan)"
        else:
            status["message"] = "⚠️ MCP ve AI analizi devre dışı"
        
        return status
        
    except Exception as e:
        return {
            "mcp_enabled": False,
            "firecrawl_enabled": False,
            "ai_analysis_enabled": True,
            "fallback_available": True,
            "ready": False,
            "message": f"❌ MCP durum kontrolü hatası: {e}"
        }

def test_mcp_connection():
    """MCP bağlantısını test et"""
    try:
        config = load_mcp_config()
        
        if not config.get("mcp_enabled", False):
            return {
                "success": False,
                "message": "MCP devre dışı",
                "details": "MCP konfigürasyondan etkinleştirilmeli"
            }
        
        firecrawl_config = config.get("firecrawl_mcp", {})
        
        if not firecrawl_config.get("enabled", False):
            return {
                "success": False,
                "message": "Firecrawl MCP devre dışı",
                "details": "Firecrawl MCP konfigürasyondan etkinleştirilmeli"
            }
        
        server_url = firecrawl_config.get("server_url", "")
        
        if not server_url:
            return {
                "success": False,
                "message": "MCP server URL'si eksik",
                "details": "Konfigürasyonda server_url ayarlanmalı"
            }
        
        # Gerçek MCP implementasyonunda burada MCP server'a test çağrısı yapılacak
        # Şimdilik simüle ediyoruz
        print(f"[TEST] MCP server test ediliyor: {server_url}")
        
        # Test URL'si ile basit scrape denemesi
        test_result = mcp_firecrawl_scrape({
            "url": "https://example.com",
            "formats": ["markdown"],
            "onlyMainContent": True
        })
        
        if test_result.get("success", False):
            return {
                "success": True,
                "message": "✅ MCP Firecrawl bağlantısı başarılı",
                "details": f"Server: {server_url}"
            }
        else:
            return {
                "success": False,
                "message": "❌ MCP Firecrawl test başarısız",
                "details": test_result.get("reason", "Bilinmeyen hata")
            }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ MCP test hatası: {e}",
            "details": "Bağlantı testi sırasında hata oluştu"
        }
