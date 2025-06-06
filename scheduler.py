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
    save_json,
    load_automation_settings,
    get_automation_status
)

load_dotenv()

class AutoTweetScheduler:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        # Ayarları yükle
        self.load_settings()
        
        # API anahtarı kontrolü
        if not self.api_key:
            print("[ERROR] OPENROUTER_API_KEY bulunamadı!")
            return
        
    def load_settings(self):
        """Ayarları yükle"""
        try:
            # Önce automation_settings.json'dan yükle
            settings = load_automation_settings()
            
            # Scheduler config varsa onu da kontrol et
            try:
                scheduler_config = load_json("scheduler_config.json")
                # Scheduler config daha yeniyse onu kullan
                if scheduler_config.get("last_updated", "") > settings.get("last_updated", ""):
                    settings.update(scheduler_config)
            except:
                pass
            
            self.auto_mode = settings.get("auto_mode", False)
            self.min_score = settings.get("min_score", 5)
            self.check_interval_hours = settings.get("check_interval_hours", 3)
            self.max_articles_per_run = settings.get("max_articles_per_run", 10)
            self.auto_post_enabled = settings.get("auto_post_enabled", False)
            self.require_manual_approval = settings.get("require_manual_approval", True)
            self.rate_limit_delay = settings.get("rate_limit_delay", 2)
            
            print(f"[CONFIG] Ayarlar yüklendi:")
            print(f"  - Otomatik mod: {'AÇIK' if self.auto_mode else 'KAPALI'}")
            print(f"  - Minimum skor: {self.min_score}")
            print(f"  - Kontrol aralığı: {self.check_interval_hours} saat")
            print(f"  - Maksimum makale: {self.max_articles_per_run}")
            print(f"  - Otomatik paylaşım: {'AÇIK' if self.auto_post_enabled else 'KAPALI'}")
            print(f"  - Manuel onay: {'GEREKLİ' if self.require_manual_approval else 'GEREKSİZ'}")
            print(f"  - Rate limit: {self.rate_limit_delay} saniye")
            
        except Exception as e:
            print(f"[ERROR] Ayarlar yüklenemedi: {e}")
            # Varsayılan ayarlar
            self.auto_mode = False
            self.min_score = 5
            self.check_interval_hours = 3
            self.max_articles_per_run = 10
            self.auto_post_enabled = False
            self.require_manual_approval = True
            self.rate_limit_delay = 2
        
    def check_working_hours(self):
        """Çalışma saatleri kontrolü"""
        try:
            status = get_automation_status()
            if not status["active"]:
                print(f"[INFO] {status['reason']} - İşlem atlanıyor")
                return False
            return True
        except Exception as e:
            print(f"[WARNING] Çalışma saatleri kontrolü hatası: {e}")
            return True  # Hata durumunda çalışmaya devam et
        
    def process_articles_automatically(self):
        """Otomatik makale işleme ve tweet paylaşımı"""
        try:
            print(f"[{datetime.now()}] Otomatik haber kontrolü başlatılıyor...")
            
            # Ayarları yeniden yükle (değişmiş olabilir)
            self.load_settings()
            
            if not self.api_key:
                print("[ERROR] API anahtarı eksik!")
                return
            
            # Çalışma saatleri kontrolü
            if not self.check_working_hours():
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
            
            # Maksimum makale sayısını sınırla
            if len(articles) > self.max_articles_per_run:
                articles = articles[:self.max_articles_per_run]
                print(f"[INFO] Maksimum {self.max_articles_per_run} makale ile sınırlandırıldı")
            
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
                    
                    # Paylaşım stratejisi
                    if self.auto_post_enabled and not self.require_manual_approval:
                        # Direkt otomatik paylaş
                        result = post_tweet(tweet_text)
                        
                        if result["success"]:
                            mark_article_as_posted(article, result)
                            print(f"[SUCCESS] Tweet otomatik paylaşıldı: {result['url']}")
                            processed_count += 1
                        else:
                            print(f"[ERROR] Tweet paylaşım hatası: {result['error']}")
                    else:
                        # Manuel onay için kaydet
                        self.save_pending_tweet(article, tweet_text, score)
                        print(f"[PENDING] Manuel onay için kaydedildi: {article['title'][:50]}...")
                        processed_count += 1
                    
                    # Rate limiting için bekleme
                    if self.rate_limit_delay > 0:
                        time.sleep(self.rate_limit_delay)
                    
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
        """Otomatik mod ayarı (komut satırından)"""
        self.auto_mode = enabled
        mode_text = "AÇIK" if enabled else "KAPALI"
        print(f"[CONFIG] Otomatik mod (komut satırı): {mode_text}")
    
    def set_min_score(self, score):
        """Minimum skor ayarı (komut satırından)"""
        self.min_score = max(1, min(10, score))
        print(f"[CONFIG] Minimum skor (komut satırı): {self.min_score}")
    
    def start_scheduler(self):
        """Zamanlayıcıyı başlat"""
        print(f"[SCHEDULER] {self.check_interval_hours} saatlik periyodik kontrol başlatılıyor...")
        
        # Dinamik zamanlama - ayarlara göre
        if self.check_interval_hours >= 1:
            schedule.every(int(self.check_interval_hours)).hours.do(self.process_articles_automatically)
        else:
            # 1 saatten az ise dakika cinsinden
            minutes = int(self.check_interval_hours * 60)
            schedule.every(minutes).minutes.do(self.process_articles_automatically)
        
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
            print("[CMD] Komut satırından otomatik mod açıldı")
        elif sys.argv[1] == "--manual":
            scheduler.set_auto_mode(False)
            print("[CMD] Komut satırından manuel mod açıldı")
        elif sys.argv[1] == "--once":
            # Tek seferlik çalıştırma
            print("[CMD] Tek seferlik çalıştırma")
            scheduler.process_articles_automatically()
            return
        elif sys.argv[1] == "--config":
            # Mevcut ayarları göster
            print("\n=== MEVCUT AYARLAR ===")
            settings = load_automation_settings()
            for key, value in settings.items():
                print(f"{key}: {value}")
            return
    
    # Zamanlayıcıyı başlat
    scheduler.start_scheduler()

if __name__ == "__main__":
    main() 