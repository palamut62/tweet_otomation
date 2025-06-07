from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import json
import time
from datetime import datetime, timedelta
from utils import (
    fetch_latest_ai_articles, generate_ai_tweet_with_mcp_analysis,
    post_tweet, mark_article_as_posted, load_json, save_json,
    get_posted_articles_summary, reset_all_data, clear_pending_tweets,
    get_data_statistics, load_automation_settings, save_automation_settings,
    get_automation_status, send_telegram_notification, test_telegram_connection,
    check_telegram_configuration, auto_detect_and_save_chat_id
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Global değişkenler
last_check_time = None
automation_running = False

@app.route('/')
def index():
    """Ana sayfa"""
    try:
        # Otomatik kontrol sistemi
        global last_check_time
        settings = load_automation_settings()
        
        if settings.get('auto_mode', False):
            current_time = datetime.now()
            check_interval_hours = settings.get('check_interval_hours', 2)
            
            # İlk çalışma veya belirlenen süre geçtiyse kontrol et
            if (last_check_time is None or 
                current_time - last_check_time >= timedelta(hours=check_interval_hours)):
                
                print(f"🔄 Otomatik kontrol başlatılıyor... (Son kontrol: {last_check_time})")
                check_and_post_articles()
                last_check_time = current_time
        
        # Sayfa verilerini hazırla
        articles = load_json("posted_articles.json")
        pending_tweets = load_json("pending_tweets.json")
        stats = get_data_statistics()
        automation_status = get_automation_status()
        
        return render_template('index.html', 
                             articles=articles[-10:], 
                             pending_tweets=pending_tweets,
                             stats=stats,
                             automation_status=automation_status,
                             last_check=last_check_time)
    except Exception as e:
        print(f"Ana sayfa hatası: {e}")
        return render_template('index.html', 
                             articles=[], 
                             pending_tweets=[],
                             stats={},
                             automation_status={},
                             error=str(e))

@app.route('/check_articles')
def check_articles():
    """Manuel makale kontrolü"""
    try:
        result = check_and_post_articles()
        flash(f"Kontrol tamamlandı: {result['message']}", 'success')
    except Exception as e:
        flash(f"Hata: {str(e)}", 'error')
    
    return redirect(url_for('index'))

def check_and_post_articles():
    """Makale kontrol ve paylaşım fonksiyonu"""
    try:
        print("🔍 Yeni makaleler kontrol ediliyor...")
        
        # Ayarları yükle
        settings = load_automation_settings()
        api_key = os.environ.get('GOOGLE_API_KEY')
        
        if not api_key:
            return {"success": False, "message": "Google API anahtarı bulunamadı"}
        
        # Yeni makaleleri çek
        articles = fetch_latest_ai_articles()
        
        if not articles:
            return {"success": True, "message": "Yeni makale bulunamadı"}
        
        posted_count = 0
        max_articles = settings.get('max_articles_per_run', 3)
        min_score = settings.get('min_score_threshold', 5)
        auto_post = settings.get('auto_post_enabled', False)
        
        for article in articles[:max_articles]:
            try:
                # Tweet oluştur
                tweet_data = generate_ai_tweet_with_mcp_analysis(article, api_key)
                
                if not tweet_data or not tweet_data.get('tweet'):
                    continue
                
                # Skor kontrolü
                impact_score = tweet_data.get('impact_score', 0)
                if impact_score < min_score:
                    print(f"⚠️ Düşük skor ({impact_score}), atlanıyor: {article['title'][:50]}...")
                    continue
                
                # Otomatik paylaşım kontrolü
                if auto_post and not settings.get('manual_approval_required', True):
                    # Direkt paylaş
                    tweet_result = post_tweet(tweet_data['tweet'], article['title'])
                    
                    if tweet_result.get('success'):
                        mark_article_as_posted(article, tweet_result)
                        posted_count += 1
                        
                        # Telegram bildirimi
                        if settings.get('telegram_notifications', False):
                            send_telegram_notification(
                                f"✅ Yeni tweet paylaşıldı!\n\n{tweet_data['tweet'][:100]}...",
                                tweet_result.get('tweet_url', ''),
                                article['title']
                            )
                        
                        print(f"✅ Tweet paylaşıldı: {article['title'][:50]}...")
                    else:
                        print(f"❌ Tweet paylaşım hatası: {tweet_result.get('error', 'Bilinmeyen hata')}")
                else:
                    # Pending listesine ekle
                    pending_tweets = load_json("pending_tweets.json")
                    pending_tweets.append({
                        "article": article,
                        "tweet_data": tweet_data,
                        "created_at": datetime.now().isoformat(),
                        "status": "pending"
                    })
                    save_json("pending_tweets.json", pending_tweets)
                    print(f"📝 Tweet onay bekliyor: {article['title'][:50]}...")
                
                # Rate limiting
                time.sleep(settings.get('rate_limit_seconds', 2))
                
            except Exception as article_error:
                print(f"❌ Makale işleme hatası: {article_error}")
                continue
        
        message = f"{len(articles)} makale bulundu, {posted_count} tweet paylaşıldı"
        return {"success": True, "message": message}
        
    except Exception as e:
        print(f"❌ Makale kontrol hatası: {e}")
        return {"success": False, "message": str(e)}

@app.route('/post_tweet', methods=['POST'])
def post_tweet_route():
    """Tweet paylaşım endpoint'i"""
    try:
        data = request.get_json()
        tweet_id = data.get('tweet_id')
        
        if not tweet_id:
            return jsonify({"success": False, "error": "Tweet ID gerekli"})
        
        # Pending tweet'i bul
        pending_tweets = load_json("pending_tweets.json")
        tweet_to_post = None
        
        for i, pending in enumerate(pending_tweets):
            if str(i) == str(tweet_id):
                tweet_to_post = pending
                break
        
        if not tweet_to_post:
            return jsonify({"success": False, "error": "Tweet bulunamadı"})
        
        # Tweet'i paylaş
        tweet_result = post_tweet(
            tweet_to_post['tweet_data']['tweet'], 
            tweet_to_post['article']['title']
        )
        
        if tweet_result.get('success'):
            # Başarılı paylaşım
            mark_article_as_posted(tweet_to_post['article'], tweet_result)
            
            # Pending listesinden kaldır
            pending_tweets = [p for i, p in enumerate(pending_tweets) if str(i) != str(tweet_id)]
            save_json("pending_tweets.json", pending_tweets)
            
            # Telegram bildirimi
            settings = load_automation_settings()
            if settings.get('telegram_notifications', False):
                send_telegram_notification(
                    f"✅ Tweet manuel olarak paylaşıldı!\n\n{tweet_to_post['tweet_data']['tweet'][:100]}...",
                    tweet_result.get('tweet_url', ''),
                    tweet_to_post['article']['title']
                )
            
            return jsonify({
                "success": True, 
                "message": "Tweet başarıyla paylaşıldı",
                "tweet_url": tweet_result.get('tweet_url', '')
            })
        else:
            return jsonify({
                "success": False, 
                "error": tweet_result.get('error', 'Bilinmeyen hata')
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/delete_tweet', methods=['POST'])
def delete_tweet_route():
    """Tweet silme endpoint'i"""
    try:
        data = request.get_json()
        tweet_id = data.get('tweet_id')
        
        if not tweet_id:
            return jsonify({"success": False, "error": "Tweet ID gerekli"})
        
        # Pending listesinden kaldır
        pending_tweets = load_json("pending_tweets.json")
        pending_tweets = [p for i, p in enumerate(pending_tweets) if str(i) != str(tweet_id)]
        save_json("pending_tweets.json", pending_tweets)
        
        return jsonify({"success": True, "message": "Tweet silindi"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/settings')
def settings():
    """Ayarlar sayfası"""
    try:
        automation_settings = load_automation_settings()
        telegram_config = check_telegram_configuration()
        
        return render_template('settings.html', 
                             settings=automation_settings,
                             telegram_config=telegram_config)
    except Exception as e:
        return render_template('settings.html', 
                             settings={},
                             telegram_config={},
                             error=str(e))

@app.route('/save_settings', methods=['POST'])
def save_settings():
    """Ayarları kaydet"""
    try:
        settings = {
            'auto_mode': request.form.get('auto_mode') == 'on',
            'check_interval_hours': int(request.form.get('check_interval_hours', 2)),
            'max_articles_per_run': int(request.form.get('max_articles_per_run', 3)),
            'min_score_threshold': int(request.form.get('min_score_threshold', 5)),
            'auto_post_enabled': request.form.get('auto_post_enabled') == 'on',
            'manual_approval_required': request.form.get('manual_approval_required') == 'on',
            'rate_limit_seconds': float(request.form.get('rate_limit_seconds', 2.0)),
            'telegram_notifications': request.form.get('telegram_notifications') == 'on',
            'last_updated': datetime.now().isoformat()
        }
        
        save_automation_settings(settings)
        flash('Ayarlar başarıyla kaydedildi!', 'success')
        
    except Exception as e:
        flash(f'Ayar kaydetme hatası: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/test_telegram')
def test_telegram():
    """Telegram bağlantı testi"""
    try:
        result = test_telegram_connection()
        if result.get('success'):
            flash('Telegram bağlantısı başarılı!', 'success')
        else:
            flash(f'Telegram hatası: {result.get("error", "Bilinmeyen hata")}', 'error')
    except Exception as e:
        flash(f'Telegram test hatası: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/auto_detect_chat_id')
def auto_detect_chat_id():
    """Telegram Chat ID otomatik algılama"""
    try:
        result = auto_detect_and_save_chat_id()
        if result.get('success'):
            flash(f'Chat ID başarıyla algılandı: {result.get("chat_id")}', 'success')
        else:
            flash(f'Chat ID algılama hatası: {result.get("error", "Bilinmeyen hata")}', 'error')
    except Exception as e:
        flash(f'Chat ID algılama hatası: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/statistics')
def statistics():
    """İstatistikler sayfası"""
    try:
        stats = get_data_statistics()
        summary = get_posted_articles_summary()
        
        return render_template('statistics.html', 
                             stats=stats,
                             summary=summary)
    except Exception as e:
        return render_template('statistics.html', 
                             stats={},
                             summary={},
                             error=str(e))

@app.route('/reset_data', methods=['POST'])
def reset_data():
    """Tüm verileri sıfırla"""
    try:
        reset_all_data()
        flash('Tüm veriler başarıyla sıfırlandı!', 'success')
    except Exception as e:
        flash(f'Veri sıfırlama hatası: {str(e)}', 'error')
    
    return redirect(url_for('statistics'))

@app.route('/clear_pending')
def clear_pending():
    """Bekleyen tweet'leri temizle"""
    try:
        clear_pending_tweets()
        flash('Bekleyen tweet\'ler temizlendi!', 'success')
    except Exception as e:
        flash(f'Temizleme hatası: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/status')
def api_status():
    """API durumu - health check"""
    try:
        stats = get_data_statistics()
        automation_status = get_automation_status()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "automation": automation_status,
            "last_check": last_check_time.isoformat() if last_check_time else None
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    # Python Anywhere için production ayarları
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug)