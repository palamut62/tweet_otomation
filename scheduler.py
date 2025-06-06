import schedule
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from utils import (
    fetch_latest_ai_articles, 
    summarize_article, 
    score_article,
    generate_ai_tweet_with_content,
    post_tweet,
    mark_article_as_posted,
    check_duplicate_articles,
    load_json,
    save_json
)

load_dotenv()

class AutoTweetScheduler:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.auto_mode = False
        self.min_score = 5  # Minimum makale skoru düşürüldü
        
        # API anahtarı kontrolü
        if not self.api_key:
            print("[ERROR] OPENROUTER_API_KEY bulunamadı!")
            return
        
    def process_articles_automatically(self):
        """Otomatik makale işleme ve tweet paylaşımı"""
        try:
            print(f"[{datetime.now()}] Otomatik haber kontrolü başlatılıyor...")
            
            if not self.api_key:
                print("[ERROR] API anahtarı eksik!")
                return
            
            # Tekrarlanan makaleleri temizle
            cleaned_count = check_duplicate_articles()
            if cleaned_count > 0:
                print(f"[INFO] {cleaned_count} eski makale temizlendi")
            
            # Yeni makaleleri çek
            articles = fetch_latest_ai_articles()
            
            if not articles:
                print("[INFO] Yeni makale bulunamadı")
                return
            
            print(f"[INFO] {len(articles)} yeni makale bulundu")
            
            processed_count = 0
            for article in articles:
                try:
                    print(f"[PROCESSING] {article['title'][:60]}...")
                    
                    # Makale skorunu hesapla
                    score = score_article(article["content"], self.api_key)
                    
                    # API hatası kontrolü
                    if score == 5 and "API" in str(score):  # Varsayılan skor API hatası olabilir
                        print(f"[WARNING] API hatası olabilir, devam ediliyor...")
                    
                    # Minimum skor kontrolü
                    if score < self.min_score:
                        print(f"[SKIP] Düşük skor ({score}): {article['title'][:50]}...")
                        continue
                    
                    # Tweet oluştur
                    tweet_text = generate_ai_tweet_with_content(article, self.api_key)
                    
                    if "oluşturulamadı" in tweet_text:
                        print(f"[ERROR] Tweet oluşturulamadı: {article['title'][:50]}...")
                        continue
                    
                    if self.auto_mode:
                        # Otomatik paylaş
                        result = post_tweet(tweet_text)
                        
                        if result["success"]:
                            mark_article_as_posted(article, result)
                            print(f"[SUCCESS] Tweet paylaşıldı: {result['url']}")
                            processed_count += 1
                        else:
                            print(f"[ERROR] Tweet paylaşım hatası: {result['error']}")
                    else:
                        # Manuel onay için kaydet
                        self.save_pending_tweet(article, tweet_text, score)
                        print(f"[PENDING] Manuel onay için kaydedildi: {article['title'][:50]}...")
                        processed_count += 1
                    
                    # Rate limiting için bekleme
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"[ERROR] Makale işleme hatası: {e}")
                    continue
            
            print(f"[COMPLETED] {processed_count} makale işlendi")
            
        except Exception as e:
            print(f"[ERROR] Otomatik işlem hatası: {e}")
    
    def save_pending_tweet(self, article, tweet_text, score):
        """Manuel onay için tweet'i kaydet"""
        try:
            pending_file = "pending_tweets.json"
            pending_tweets = load_json(pending_file)
            
            pending_tweet = {
                "article": article,
                "tweet_text": tweet_text,
                "score": score,
                "created_date": datetime.now().isoformat(),
                "status": "pending"
            }
            
            pending_tweets.append(pending_tweet)
            save_json(pending_file, pending_tweets)
            
        except Exception as e:
            print(f"Pending tweet kaydetme hatası: {e}")
    
    def set_auto_mode(self, enabled):
        """Otomatik mod ayarı"""
        self.auto_mode = enabled
        mode_text = "AÇIK" if enabled else "KAPALI"
        print(f"[CONFIG] Otomatik mod: {mode_text}")
    
    def set_min_score(self, score):
        """Minimum skor ayarı"""
        self.min_score = max(1, min(10, score))
        print(f"[CONFIG] Minimum skor: {self.min_score}")
    
    def start_scheduler(self):
        """Zamanlayıcıyı başlat"""
        print("[SCHEDULER] 3 saatlik periyodik kontrol başlatılıyor...")
        
        # Her 3 saatte bir çalıştır
        schedule.every(3).hours.do(self.process_articles_automatically)
        
        # İlk çalıştırma
        self.process_articles_automatically()
        
        # Sürekli çalışma döngüsü
        while True:
            schedule.run_pending()
            time.sleep(60)  # Her dakika kontrol et

def main():
    """Ana çalıştırma fonksiyonu"""
    scheduler = AutoTweetScheduler()
    
    # Komut satırı argümanları
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            scheduler.set_auto_mode(True)
        elif sys.argv[1] == "--manual":
            scheduler.set_auto_mode(False)
        elif sys.argv[1] == "--once":
            # Tek seferlik çalıştırma
            scheduler.process_articles_automatically()
            return
    
    # Zamanlayıcıyı başlat
    scheduler.start_scheduler()

if __name__ == "__main__":
    main() 