import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from utils import (
    fetch_latest_ai_articles, summarize_article, score_article,
    categorize_article, generate_ai_tweet_with_content, create_pdf,
    load_json, save_json, post_tweet, mark_article_as_posted,
    check_duplicate_articles, setup_twitter_api, get_posted_articles_summary,
    reset_all_data, clear_pending_tweets, get_data_statistics,
    load_automation_settings, save_automation_settings, get_automation_status,
    update_scheduler_settings, validate_automation_settings,
    send_telegram_notification, test_telegram_connection, get_telegram_chat_id,
    check_telegram_configuration, save_telegram_chat_id, auto_detect_and_save_chat_id,
    load_mcp_config, save_mcp_config, get_mcp_status, test_mcp_connection
)

load_dotenv()

# API anahtarları kontrolü
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

if not GOOGLE_API_KEY:
    st.error("❌ GOOGLE_API_KEY .env dosyasında bulunamadı!")
    st.stop()

# Sayfa yapılandırması
st.set_page_config(
    page_title="🤖 AI Tweet Bot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI Tweet Bot – Gelişmiş Panel")

# Sidebar - Ayarlar
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # Twitter API durumu
    twitter_client = setup_twitter_api()
    if twitter_client:
        st.success("✅ Twitter API Bağlı")
    else:
        st.error("❌ Twitter API Bağlantısı Yok")
        st.info("Twitter API anahtarlarını .env dosyasına ekleyin")
    
    # Otomatikleştirme Ayarları
    st.header("🤖 Otomatikleştirme Ayarları")
    
    # Mevcut ayarları yükle
    automation_settings = load_automation_settings()
    automation_status = get_automation_status()
    
    # Otomatikleştirme durumu
    if automation_status["active"]:
        st.success(f"🟢 Otomatikleştirme: {automation_status['reason']}")
    else:
        st.warning(f"🟡 Otomatikleştirme: {automation_status['reason']}")
    
    # Ayarlar formu
    with st.expander("🔧 Otomatikleştirme Ayarları", expanded=False):
        # Temel ayarlar
        st.subheader("📋 Temel Ayarlar")
        
        auto_mode = st.checkbox(
            "🔄 Otomatik Mod Aktif", 
            value=automation_settings.get("auto_mode", False),
            help="Otomatik haber kontrolü ve işleme"
        )
        
        auto_post = st.checkbox(
            "📤 Otomatik Tweet Paylaşımı", 
            value=automation_settings.get("auto_post_enabled", False),
            help="Onay beklemeden direkt tweet paylaş"
        )
        
        manual_approval = st.checkbox(
            "✋ Manuel Onay Gerekli", 
            value=automation_settings.get("require_manual_approval", True),
            help="Tweet'ler paylaşılmadan önce onay beklesin"
        )
        
        min_score = st.slider(
            "📊 Minimum Makale Skoru", 
            1, 10, 
            automation_settings.get("min_score", 5),
            help="Bu skorun altındaki makaleler işlenmez"
        )
        
        # Zamanlama ayarları
        st.subheader("⏰ Zamanlama Ayarları")
        
        check_interval = st.selectbox(
            "🔄 Kontrol Aralığı",
            options=[0.5, 1, 2, 3, 6, 12, 24],
            index=[0.5, 1, 2, 3, 6, 12, 24].index(automation_settings.get("check_interval_hours", 3)),
            format_func=lambda x: f"{x} saat" if x >= 1 else f"{int(x*60)} dakika",
            help="Ne sıklıkla yeni haber kontrol edilsin"
        )
        
        max_articles = st.number_input(
            "📰 Maksimum Makale Sayısı (Her Çalıştırmada)",
            min_value=1, max_value=50,
            value=automation_settings.get("max_articles_per_run", 10),
            help="Her kontrol sırasında işlenecek maksimum makale sayısı"
        )
        
        rate_delay = st.number_input(
            "⏱️ API Gecikme Süresi (saniye)",
            min_value=0.0, max_value=60.0, step=0.5,
            value=float(automation_settings.get("rate_limit_delay", 2)),
            help="API çağrıları arasındaki bekleme süresi"
        )
        
        # Çalışma saatleri
        st.subheader("🕒 Çalışma Saatleri")
        
        working_hours_only = st.checkbox(
            "🕘 Sadece Çalışma Saatlerinde Çalış",
            value=automation_settings.get("working_hours_only", False),
            help="Belirtilen saatler dışında otomatik işlem yapma"
        )
        
        if working_hours_only:
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input(
                    "🌅 Başlangıç",
                    value=datetime.strptime(automation_settings.get("working_hours_start", "09:00"), "%H:%M").time()
                )
            with col2:
                end_time = st.time_input(
                    "🌆 Bitiş",
                    value=datetime.strptime(automation_settings.get("working_hours_end", "18:00"), "%H:%M").time()
                )
            
            weekend_enabled = st.checkbox(
                "📅 Hafta Sonu Çalış",
                value=automation_settings.get("weekend_enabled", True),
                help="Cumartesi ve Pazar günleri de çalış"
            )
        else:
            start_time = datetime.strptime("09:00", "%H:%M").time()
            end_time = datetime.strptime("18:00", "%H:%M").time()
            weekend_enabled = True
        
        # Ayarları kaydet butonu
        if st.button("💾 Ayarları Kaydet", type="primary", key="automation_save_settings"):
            new_settings = {
                "auto_mode": auto_mode,
                "min_score": min_score,
                "check_interval_hours": check_interval,
                "max_articles_per_run": max_articles,
                "auto_post_enabled": auto_post,
                "require_manual_approval": manual_approval,
                "working_hours_only": working_hours_only,
                "working_hours_start": start_time.strftime("%H:%M"),
                "working_hours_end": end_time.strftime("%H:%M"),
                "weekend_enabled": weekend_enabled,
                "rate_limit_delay": rate_delay
            }
            
            # Ayarları doğrula
            validation_errors = validate_automation_settings(new_settings)
            
            if validation_errors:
                for error in validation_errors:
                    st.error(f"❌ {error}")
            else:
                # Ayarları kaydet
                save_result = save_automation_settings(new_settings)
                
                if save_result["success"]:
                    # Scheduler ayarlarını güncelle
                    update_result = update_scheduler_settings()
                    
                    st.success(save_result["message"])
                    if update_result["success"]:
                        st.info("🔄 Scheduler ayarları güncellendi")
                    else:
                        st.warning(f"⚠️ {update_result['message']}")
                    
                    st.rerun()
                else:
                    st.error(save_result["message"])
        
        # Ayarları sıfırla butonu
        if st.button("🔄 Varsayılan Ayarlara Dön", type="secondary", key="automation_reset_defaults"):
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
                "rate_limit_delay": 2
            }
            
            save_result = save_automation_settings(default_settings)
            if save_result["success"]:
                st.success("✅ Varsayılan ayarlar yüklendi")
                st.rerun()
            else:
                st.error(save_result["message"])
    
    # Telegram Ayarları
    st.header("📱 Telegram Bildirimleri")
    
    # Telegram konfigürasyonunu kontrol et
    config_status = check_telegram_configuration()
    
    # Durum göstergesi
    if config_status["status"] == "ready":
        st.success(config_status["message"])
    elif config_status["status"] == "partial":
        st.warning(config_status["message"])
    elif config_status["status"] == "missing":
        st.error(config_status["message"])
    else:
        st.error(config_status["message"])
    
    with st.expander("🔧 Telegram Bot Ayarları", expanded=False):
        current_settings = load_automation_settings()
        
        # Bot Token durumu
        st.subheader("🤖 Bot Token")
        
        env_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        settings_bot_token = current_settings.get("telegram_bot_token", "")
        
        if env_bot_token:
            st.success("✅ TELEGRAM_BOT_TOKEN (Environment Variable)")
            st.code(f"Token: {env_bot_token[:10]}...{env_bot_token[-4:] if len(env_bot_token) > 14 else ''}")
            bot_token = env_bot_token
        elif settings_bot_token:
            st.info("ℹ️ Bot Token (Ayarlar Dosyası)")
            st.code(f"Token: {settings_bot_token[:10]}...{settings_bot_token[-4:] if len(settings_bot_token) > 14 else ''}")
            bot_token = settings_bot_token
        else:
            st.error("❌ Bot Token eksik")
            st.info("📝 .env dosyasına TELEGRAM_BOT_TOKEN ekleyin veya aşağıdan manuel girin")
            bot_token = ""
        
        # Chat ID durumu ve otomatik tespit
        st.subheader("💬 Chat ID")
        
        current_chat_id = current_settings.get("telegram_chat_id", "")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if current_chat_id:
                st.success(f"✅ Chat ID ayarlanmış: {current_chat_id}")
            else:
                st.warning("⚠️ Chat ID ayarlanmamış")
        
        with col2:
            # Otomatik Chat ID tespit butonu
            if bot_token and st.button("🔍 Chat ID Bul & Kaydet", help="Otomatik chat ID tespit et ve kaydet", key="telegram_auto_detect_chat_id"):
                with st.spinner("Chat ID tespit ediliyor ve kaydediliyor..."):
                    result = auto_detect_and_save_chat_id()
                    
                    if result["success"]:
                        if result["auto_detected"]:
                            st.success(result["message"])
                            st.info(f"📋 Tespit edilen: {result['chat_info']['title']} ({result['chat_info']['type']})")
                            
                            # Diğer chat'ler varsa göster
                            if len(result.get("all_chats", [])) > 1:
                                st.info("🔍 Diğer bulunan chat'ler:")
                                for chat in result["all_chats"][1:]:
                                    st.text(f"• {chat['chat_id']} - {chat['title']} ({chat['type']})")
                        else:
                            st.info(result["message"])
                        
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
        
        st.markdown("---")
        
        telegram_enabled = st.checkbox(
            "📱 Telegram Bildirimleri Aktif",
            value=current_settings.get("telegram_notifications", True),  # Varsayılan True
            help="Her tweet paylaşıldığında Telegram'a bildirim gönder"
        )
        
        # Manuel ayarlar (sadece gerektiğinde)
        if not env_bot_token:
            st.subheader("⚙️ Manuel Bot Token")
            st.info("💡 Environment variable yoksa buradan bot token girebilirsiniz")
            
            manual_bot_token = st.text_input(
                "🤖 Bot Token (Manuel)",
                value=settings_bot_token,
            type="password",
            help="@BotFather'dan aldığınız bot token'ı"
        )
        
            if manual_bot_token != settings_bot_token:
                bot_token = manual_bot_token
        
        # Manuel Chat ID değiştirme
        if current_chat_id:
            st.subheader("🔧 Chat ID Değiştir")
            
            new_chat_id = st.text_input(
                "💬 Yeni Chat ID",
                value=current_chat_id,
                help="Farklı bir chat ID kullanmak istiyorsanız"
            )
            
            if new_chat_id != current_chat_id and st.button("💾 Chat ID'yi Güncelle", key="telegram_update_chat_id"):
                save_result = save_telegram_chat_id(new_chat_id)
                if save_result["success"]:
                    st.success(save_result["message"])
                    st.rerun()
                else:
                    st.error(f"❌ {save_result['error']}")
        
        # Test butonu
        if bot_token and current_chat_id and st.button("🧪 Bağlantıyı Test Et", key="telegram_test_connection"):
            with st.spinner("Test mesajı gönderiliyor..."):
                result = test_telegram_connection()
                if result["success"]:
                    st.success(f"✅ Test başarılı! Bot: {result['bot_name']} (@{result['bot_username']})")
                else:
                    st.error(f"❌ Test başarısız: {result['error']}")
        
        # Ayarları kaydet
        if st.button("💾 Telegram Ayarlarını Kaydet", key="telegram_save_settings"):
            telegram_settings = current_settings.copy()
            telegram_settings.update({
                "telegram_notifications": telegram_enabled
            })
            
            # Manuel bot token varsa kaydet
            if not env_bot_token and 'manual_bot_token' in locals() and manual_bot_token:
                telegram_settings["telegram_bot_token"] = manual_bot_token.strip()
            
            save_result = save_automation_settings(telegram_settings)
            if save_result["success"]:
                st.success("✅ Telegram ayarları kaydedildi!")
                st.rerun()
            else:
                st.error(f"❌ Kaydetme hatası: {save_result['message']}")
        
        # Telegram kurulum rehberi
        if st.button("📖 Kurulum Rehberini Göster", key="telegram_show_guide"):
            st.info("""
            **🚀 Hızlı Kurulum (Önerilen):**
            
            1. **Bot Oluşturma:**
            - Telegram'da @BotFather'a mesaj gönderin
            - `/newbot` komutunu kullanın
            - Bot adını ve kullanıcı adını belirleyin
            - Bot token'ınızı kopyalayın
            
            2. **.env Dosyası Ayarlama:**
               - Proje klasöründeki .env dosyasını açın
               - Şu satırı ekleyin:
               ```
               TELEGRAM_BOT_TOKEN=your_bot_token_here
               ```
               (Chat ID'yi .env'e eklemenize gerek yok!)
            
            3. **Otomatik Chat ID Kurulumu:**
               - Uygulamayı yeniden başlatın
               - Bot'unuza Telegram'dan bir mesaj gönderin
               - "🔍 Chat ID Bul & Kaydet" butonuna tıklayın
               - Chat ID otomatik tespit edilip kaydedilecek
            
            4. **Test:**
               - "🧪 Bağlantıyı Test Et" butonuna tıklayın
            - Test mesajını Telegram'da kontrol edin
            
            **💡 Avantajlar:**
            - Chat ID environment variable'da saklanmaz (daha esnek)
            - Farklı chat'lere kolayca geçiş yapabilirsiniz
            - Otomatik tespit ve kaydetme
            
            **⚙️ Manuel Ayarlar:**
            - Environment variable yoksa manuel bot token girebilirsiniz
            - Chat ID'yi manuel olarak da değiştirebilirsiniz
            """)
    
    # Scheduler kontrol butonları
    st.header("🎮 Scheduler Kontrolü")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Otomatik Başlat", help="Otomatik haber kontrolü ve tweet oluşturma", key="scheduler_auto_start"):
            with st.spinner("Otomatik işlem başlatılıyor..."):
                try:
                    # Scheduler fonksiyonunu doğrudan çağır
                    from scheduler import run_automation_once
                    result = run_automation_once()
                    
                    if result.get("success", False):
                        st.success(f"✅ {result.get('message', 'İşlem tamamlandı')}")
                        if result.get("new_articles", 0) > 0:
                            st.info(f"📰 {result['new_articles']} yeni makale işlendi")
                        if result.get("pending_tweets", 0) > 0:
                            st.info(f"📝 {result['pending_tweets']} tweet manuel onay için bekliyor")
                    else:
                        st.warning(f"⚠️ {result.get('message', 'İşlem tamamlandı ama yeni içerik bulunamadı')}")
                    
                    # Sayfayı yenile
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Hata: {str(e)}")
    
    with col2:
        if st.button("⏯️ Tek Kontrol", help="Bir kez haber kontrolü yap", key="scheduler_single_check"):
            with st.spinner("Haberler kontrol ediliyor..."):
                try:
                    # Sadece haber çekme işlemi
                    articles = fetch_latest_ai_articles()
                    
                    if articles:
                        new_articles = [a for a in articles if not a.get('already_posted', False)]
                        st.success(f"✅ {len(new_articles)} yeni makale bulundu!")
                        st.session_state.articles = articles
                    else:
                        st.warning("⚠️ Yeni makale bulunamadı")
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Hata: {str(e)}")
    
    # Otomatik/Manuel mod (eski - geriye uyumluluk için)
    auto_mode_legacy = st.checkbox("🔄 Otomatik Tweet Paylaşımı (Eski)", value=False)
    
    # Minimum skor ayarı (eski - geriye uyumluluk için)
    min_score_legacy = st.slider("📊 Minimum Makale Skoru (Eski)", 1, 10, 5)
    
    # İstatistikler
    st.header("📈 İstatistikler")
    posted_summary = get_posted_articles_summary()
    pending_tweets = load_json("pending_tweets.json")
    data_stats = get_data_statistics()
    
    st.metric("Toplam Paylaşılan", posted_summary["total_posted"])
    st.metric("Son 7 Gün", posted_summary["recent_posted"])
    st.metric("Bekleyen Tweet", data_stats["pending_tweets"])
    
    # Detaylı istatistikler
    with st.expander("📊 Detaylı İstatistikler"):
        st.write(f"**Paylaşılan Makaleler:** {data_stats['posted_articles']}")
        st.write(f"**Bekleyen Tweet'ler:** {data_stats['pending_tweets']}")
        st.write(f"**Paylaşılmış Tweet'ler:** {data_stats['posted_tweets_in_pending']}")
        st.write(f"**Özetler:** {data_stats['summaries']}")
        st.write(f"**Hashtag'ler:** {data_stats['hashtags']}")
        st.write(f"**Hesaplar:** {data_stats['accounts']}")
    
    # Veri yönetimi
    st.header("🗂️ Veri Yönetimi")
    
    # Bekleyen tweet'leri temizle
    if st.button("🧹 Bekleyen Tweet'leri Temizle", type="secondary", key="data_clear_pending"):
        with st.spinner("Bekleyen tweet'ler temizleniyor..."):
            result = clear_pending_tweets()
            if result["success"]:
                st.success(result["message"])
                st.rerun()
            else:
                st.error(result["message"])
    
    # Tüm verileri sıfırla
    st.markdown("---")
    st.markdown("⚠️ **Dikkat: Geri alınamaz işlemler**")
    
    if st.button("🗑️ TÜM VERİLERİ SIFIRLA", type="primary", key="data_reset_all"):
        # Onay modalı
        if st.session_state.get('confirm_reset', False):
            with st.spinner("Tüm veriler sıfırlanıyor..."):
                result = reset_all_data()
                if result["success"]:
                    st.success(result["message"])
                    st.success("🎉 Uygulama temiz bir duruma getirildi!")
                    st.session_state['confirm_reset'] = False
                    st.rerun()
                else:
                    st.error(result["message"])
        else:
            st.session_state['confirm_reset'] = True
            st.warning("⚠️ Bu işlem tüm verileri silecek! Emin misiniz?")
            st.rerun()
    
    # Onay iptal butonu
    if st.session_state.get('confirm_reset', False):
        if st.button("❌ İptal Et", key="data_cancel_reset"):
            st.session_state['confirm_reset'] = False
            st.rerun()
    
    # Son paylaşılan makaleler
    if posted_summary["recent_articles"]:
        st.subheader("🕒 Son Paylaşılanlar")
        for article in posted_summary["recent_articles"]:
            with st.expander(f"✅ {article.get('title', 'Tweet')[:30]}..."):
                st.markdown(f"**Tarih:** {article.get('posted_date', '')[:16]}")
                if article.get('tweet_url'):
                    st.markdown(f"[Tweet'i Görüntüle]({article['tweet_url']})")

# Ana içerik alanları - Sekme yapısı
tab1, tab2, tab3 = st.tabs(["📰 Haber Yönetimi", "⚙️ MCP Konfigürasyonu", "📊 Analiz & Raporlar"])

with tab1:
    # Haber yönetimi sekmesi
    col1, col2 = st.columns([2, 1])

with col1:
    st.header("📰 Yeni Haberler")
    
    # Haber çekme butonu
    if st.button("🔄 Haberleri Yenile", type="primary", key="news_refresh"):
        with st.spinner("Haberler çekiliyor ve tekrar kontrolü yapılıyor..."):
            # Tekrarlanan makaleleri temizle
            cleaned_count = check_duplicate_articles()
            if cleaned_count > 0:
                st.info(f"🧹 {cleaned_count} eski makale temizlendi")
            
            articles = fetch_latest_ai_articles()
            st.session_state.articles = articles
            
            if articles:
                st.success(f"✅ {len(articles)} yeni makale bulundu!")
                st.info("💡 Sadece daha önce paylaşılmamış haberler gösteriliyor")
            else:
                st.warning("⚠️ Yeni makale bulunamadı - Tüm haberler daha önce paylaşılmış olabilir")

    # Makaleleri göster
    if 'articles' in st.session_state and st.session_state.articles:
        for idx, article in enumerate(st.session_state.articles):
            # Sadece yeni makaleleri göster
            if not article.get('already_posted', False):
                with st.expander(f"🆕 {article['title'][:80]}..."):
                    st.markdown(f"**🔗 URL:** {article['url']}")
                    st.markdown(f"**📅 Çekilme Tarihi:** {article.get('fetch_date', '')[:16]}")
                    
                    # Yeni makale işareti
                    st.success("🆕 Bu makale daha önce paylaşılmamış")
                    
                    # İçerik önizlemesi
                    if article.get('content'):
                        st.markdown(f"**📄 İçerik Önizlemesi:**")
                        st.text(article['content'][:300] + "..." if len(article['content']) > 300 else article['content'])
                    
                    # Analiz butonu
                    if st.button(f"📊 Analiz Et", key=f"analyze_{idx}"):
                        with st.spinner("Analiz ediliyor..."):
                            score = score_article(article['content'], GOOGLE_API_KEY)
                            category = categorize_article(article['content'], GOOGLE_API_KEY)
                            summary = summarize_article(article['content'], GOOGLE_API_KEY)
                            
                            st.info(f"**Skor:** {score}/10 | **Kategori:** {category}")
                            st.success(f"**Özet:** {summary}")
                            
                            # Session state'e kaydet
                            article['score'] = score
                            article['category'] = category
                            article['summary'] = summary
                    
                    # Tweet oluştur butonu
                    if st.button(f"🐦 Tweet Oluştur", key=f"tweet_create_{idx}"):
                        with st.spinner("Tweet oluşturuluyor..."):
                            tweet_text = generate_ai_tweet_with_content(article, GOOGLE_API_KEY)
                            st.session_state[f'generated_tweet_{idx}'] = tweet_text
                            st.success("✅ Tweet oluşturuldu!")
                            st.rerun()
                    
                    # Tweet göster
                    if f'generated_tweet_{idx}' in st.session_state:
                        tweet_text = st.session_state[f'generated_tweet_{idx}']
                        
                        st.markdown("**🐦 Oluşturulan Tweet:**")
                        st.text_area("Tweet İçeriği", tweet_text, height=100, key=f"tweet_display_{idx}", label_visibility="collapsed")
                        
                        # Skor kontrolü
                        article_score = article.get('score', 0)
                        if article_score > 0 and article_score < min_score:
                            st.warning(f"⚠️ Düşük skor ({article_score}). Minimum: {min_score}")
                        elif article_score >= min_score:
                            st.success(f"✅ Yeterli skor ({article_score}). Minimum: {min_score}")
                        
                        # Paylaşım butonları
                        if st.button(f"📤 Tweet Paylaş", key=f"tweet_share_{idx}", disabled=not twitter_client):
                            if twitter_client:
                                with st.spinner("Tweet paylaşılıyor..."):
                                    result = post_tweet(tweet_text, article.get('title', ''))
                                    
                                    if result["success"]:
                                        mark_article_as_posted(article, result)
                                        success_msg = f"✅ Tweet paylaşıldı! [Link]({result['url']})"
                                        if result.get('telegram_sent'):
                                            success_msg += "\n📱 Telegram bildirimi gönderildi!"
                                        st.success(success_msg)
                                        
                                        # Session state'den kaldır
                                        if f'generated_tweet_{idx}' in st.session_state:
                                            del st.session_state[f'generated_tweet_{idx}']
                                        
                                        # Makaleyi listeden kaldır
                                        if 'articles' in st.session_state:
                                            st.session_state.articles[idx]['already_posted'] = True
                                        
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Hata: {result['error']}")
                            else:
                                st.error("❌ Twitter API bağlantısı yok")
                        
                        # Kaydet butonu
                        if st.button(f"💾 Kaydet", key=f"tweet_save_{idx}"):
                            # Pending tweets'e kaydet
                            pending_tweets = load_json("pending_tweets.json")
                            pending_tweet = {
                                "article": article,
                                "tweet_text": tweet_text,
                                "score": article.get('score', 0),
                                "created_date": datetime.now().isoformat(),
                                "status": "pending"
                            }
                            pending_tweets.append(pending_tweet)
                            save_json("pending_tweets.json", pending_tweets)
                            st.success("💾 Tweet kaydedildi!")
                        
                        # Düzenle butonu
                        if st.button(f"✏️ Düzenle", key=f"tweet_edit_{idx}"):
                            st.session_state[f'editing_tweet_{idx}'] = True
                            st.rerun()
                    
                    # Düzenleme modu
                    if st.session_state.get(f'editing_tweet_{idx}', False):
                        current_tweet = st.session_state.get(f'generated_tweet_{idx}', '')
                        new_tweet = st.text_area("Yeni Tweet:", current_tweet, key=f"tweet_edit_text_{idx}")
                        
                        if st.button(f"💾 Kaydet", key=f"tweet_edit_save_{idx}"):
                            st.session_state[f'generated_tweet_{idx}'] = new_tweet
                            st.session_state[f'editing_tweet_{idx}'] = False
                            st.success("💾 Değişiklikler kaydedildi!")
                            st.rerun()
                        
                        if st.button(f"❌ İptal", key=f"tweet_edit_cancel_{idx}"):
                            st.session_state[f'editing_tweet_{idx}'] = False
                            st.rerun()
    else:
        st.info("📭 Henüz haber çekilmedi. 'Haberleri Yenile' butonuna tıklayın.")

with col2:
    st.header("⏳ Bekleyen Tweet'ler")
    
    # Bekleyen tweet'leri göster
    pending_tweets = load_json("pending_tweets.json")
    pending_list = [t for t in pending_tweets if t.get("status") == "pending"]
    
    if pending_list:
        st.info(f"📊 {len(pending_list)} bekleyen tweet var")
        for idx, pending in enumerate(pending_list):
            with st.expander(f"📝 {pending['article']['title'][:40]}..."):
                st.markdown(f"**Skor:** {pending.get('score', 'N/A')}/10")
                st.markdown(f"**Tarih:** {pending.get('created_date', '')[:16]}")
                
                st.text_area("Tweet İçeriği:", pending['tweet_text'], height=80, key=f"pending_display_{idx}", label_visibility="collapsed")
                
                if st.button(f"✅ Onayla", key=f"pending_approve_{idx}"):
                    if twitter_client:
                        result = post_tweet(pending['tweet_text'], pending['article'].get('title', ''))
                        if result["success"]:
                            mark_article_as_posted(pending['article'], result)
                            # Pending'den kaldır
                            pending['status'] = 'posted'
                            save_json("pending_tweets.json", pending_tweets)
                            success_msg = "✅ Tweet paylaşıldı!"
                            if result.get('telegram_sent'):
                                success_msg += "\n📱 Telegram bildirimi gönderildi!"
                            st.success(success_msg)
                            st.rerun()
                        else:
                            st.error(f"❌ Hata: {result['error']}")
                    else:
                        st.error("❌ Twitter API bağlantısı yok")
                
                if st.button(f"❌ Reddet", key=f"pending_reject_{idx}"):
                    pending['status'] = 'rejected'
                    save_json("pending_tweets.json", pending_tweets)
                    st.info("❌ Tweet reddedildi")
                    st.rerun()
                
                if st.button(f"✏️ Düzenle", key=f"pending_edit_{idx}"):
                    st.session_state[f'editing_pending_{idx}'] = True
                    st.rerun()
                
                # Düzenleme modu
                if st.session_state.get(f'editing_pending_{idx}', False):
                    new_tweet = st.text_area("Yeni Tweet:", pending['tweet_text'], key=f"pending_edit_text_{idx}")
                    
                    if st.button(f"💾 Kaydet", key=f"pending_edit_save_{idx}"):
                        pending['tweet_text'] = new_tweet
                        save_json("pending_tweets.json", pending_tweets)
                        st.session_state[f'editing_pending_{idx}'] = False
                        st.success("💾 Değişiklikler kaydedildi!")
                        st.rerun()
                    
                    if st.button(f"❌ İptal", key=f"pending_edit_cancel_{idx}"):
                        st.session_state[f'editing_pending_{idx}'] = False
                        st.rerun()
    else:
        st.info("📭 Bekleyen tweet yok")
    
    # Geçmiş tweet'ler
    st.header("📜 Son Paylaşılanlar")
    
    recent_articles = posted_summary.get("recent_articles", [])
    if recent_articles:
        for article in recent_articles:
            with st.expander(f"✅ {article.get('title', 'Tweet')[:30]}..."):
                st.markdown(f"**Tarih:** {article.get('posted_date', '')[:16]}")
                if article.get('tweet_url'):
                    st.markdown(f"**Link:** [Tweet'i Görüntüle]({article['tweet_url']})")
                st.markdown(f"**URL:** {article.get('url', 'N/A')}")
    else:
        st.info("📭 Henüz paylaşılan tweet yok")

with tab2:
    # MCP Konfigürasyon sekmesi
    st.header("🔧 MCP (Model Context Protocol) Konfigürasyonu")
    
    # MCP durumu
    mcp_status = get_mcp_status()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if mcp_status["ready"]:
            st.success(mcp_status["message"])
        elif mcp_status["mcp_enabled"]:
            st.warning(mcp_status["message"])
        else:
            st.info(mcp_status["message"])
    
    with col2:
        if st.button("🧪 MCP Bağlantısını Test Et", key="mcp_test_connection"):
            with st.spinner("MCP bağlantısı test ediliyor..."):
                test_result = test_mcp_connection()
                if test_result["success"]:
                    st.success(test_result["message"])
                    st.info(test_result["details"])
                else:
                    st.error(test_result["message"])
                    st.warning(test_result["details"])
    
    # MCP ayarları
    st.subheader("⚙️ MCP Ayarları")
    
    # Mevcut konfigürasyonu yükle
    mcp_config = load_mcp_config()
    
    # Ana MCP ayarları
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔧 Genel MCP Ayarları**")
        
        mcp_enabled = st.checkbox(
            "🔌 MCP Etkin",
            value=mcp_config.get("mcp_enabled", False),
            help="Model Context Protocol desteğini etkinleştir"
        )
        
        firecrawl_enabled = st.checkbox(
            "🔥 Firecrawl MCP Etkin",
            value=mcp_config.get("firecrawl_mcp", {}).get("enabled", False),
            help="Firecrawl MCP ile gelişmiş web scraping",
            disabled=not mcp_enabled
        )
        
        ai_analysis_enabled = st.checkbox(
            "🤖 AI Analizi Etkin",
            value=mcp_config.get("ai_analysis", {}).get("enabled", True),
            help="AI ile gelişmiş tweet ve hashtag analizi"
        )
    
    with col2:
        st.markdown("**🌐 Firecrawl MCP Ayarları**")
        
        server_url = st.text_input(
            "🖥️ MCP Server URL",
            value=mcp_config.get("firecrawl_mcp", {}).get("server_url", "http://localhost:3000"),
            help="Firecrawl MCP server adresi",
            disabled=not firecrawl_enabled
        )
        
        api_key = st.text_input(
            "🔑 Firecrawl API Key",
            value=mcp_config.get("firecrawl_mcp", {}).get("api_key", ""),
            type="password",
            help="Firecrawl API anahtarı (opsiyonel)",
            disabled=not firecrawl_enabled
        )
        
        timeout = st.number_input(
            "⏱️ Timeout (saniye)",
            min_value=10, max_value=120,
            value=mcp_config.get("firecrawl_mcp", {}).get("timeout", 30),
            help="MCP çağrıları için timeout süresi",
            disabled=not firecrawl_enabled
        )
        
        retry_count = st.number_input(
            "🔄 Yeniden Deneme Sayısı",
            min_value=1, max_value=10,
            value=mcp_config.get("firecrawl_mcp", {}).get("retry_count", 3),
            help="Başarısız çağrılar için yeniden deneme sayısı",
            disabled=not firecrawl_enabled
        )
    
    # İçerik çıkarma ayarları
    st.subheader("📄 İçerik Çıkarma Ayarları")
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_content_length = st.number_input(
            "📏 Maksimum İçerik Uzunluğu",
            min_value=500, max_value=10000,
            value=mcp_config.get("content_extraction", {}).get("max_content_length", 2500),
            help="Çıkarılacak maksimum karakter sayısı"
        )
        
        min_content_length = st.number_input(
            "📐 Minimum İçerik Uzunluğu",
            min_value=50, max_value=1000,
            value=mcp_config.get("content_extraction", {}).get("min_content_length", 100),
            help="Geçerli sayılacak minimum karakter sayısı"
        )
    
    with col2:
        wait_time = st.number_input(
            "⏳ Sayfa Yükleme Bekleme Süresi (ms)",
            min_value=1000, max_value=10000,
            value=mcp_config.get("content_extraction", {}).get("wait_time", 3000),
            help="Dinamik içerik için bekleme süresi"
        )
        
        only_main_content = st.checkbox(
            "📰 Sadece Ana İçerik",
            value=mcp_config.get("content_extraction", {}).get("only_main_content", True),
            help="Navigasyon, footer vb. kısımları filtrele"
        )
        
        remove_base64_images = st.checkbox(
            "🖼️ Base64 Resimleri Kaldır",
            value=mcp_config.get("content_extraction", {}).get("remove_base64_images", True),
            help="Base64 kodlu resimleri içerikten çıkar"
        )
    
    # AI analizi ayarları
    st.subheader("🤖 AI Analizi Ayarları")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ai_max_tokens = st.number_input(
            "🎯 Maksimum Token",
            min_value=100, max_value=1000,
            value=mcp_config.get("ai_analysis", {}).get("max_tokens", 300),
            help="AI analizi için maksimum token sayısı",
            disabled=not ai_analysis_enabled
        )
        
        ai_temperature = st.slider(
            "🌡️ Temperature",
            min_value=0.0, max_value=1.0, step=0.1,
            value=mcp_config.get("ai_analysis", {}).get("temperature", 0.7),
            help="AI yaratıcılık seviyesi (0=deterministik, 1=yaratıcı)",
            disabled=not ai_analysis_enabled
        )
    
    with col2:
        ai_model = st.selectbox(
            "🧠 AI Model",
            options=[
                "deepseek/deepseek-chat-v3-0324:free",
                "meta-llama/llama-3.2-3b-instruct:free",
                "microsoft/phi-3-mini-128k-instruct:free",
                "google/gemma-2-9b-it:free"
            ],
            index=0,
            help="Kullanılacak AI modeli",
            disabled=not ai_analysis_enabled
        )
        
        fallback_enabled = st.checkbox(
            "🔄 Fallback Etkin",
            value=mcp_config.get("ai_analysis", {}).get("fallback_enabled", True),
            help="AI analizi başarısızsa eski yöntemi kullan",
            disabled=not ai_analysis_enabled
        )
    
    # Ayarları kaydet
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("💾 MCP Ayarlarını Kaydet", type="primary", key="mcp_save_settings"):
            new_config = {
                "mcp_enabled": mcp_enabled,
                "firecrawl_mcp": {
                    "enabled": firecrawl_enabled,
                    "server_url": server_url.strip(),
                    "api_key": api_key.strip(),
                    "timeout": timeout,
                    "retry_count": retry_count,
                    "fallback_enabled": True
                },
                "content_extraction": {
                    "max_content_length": max_content_length,
                    "min_content_length": min_content_length,
                    "wait_time": wait_time,
                    "remove_base64_images": remove_base64_images,
                    "only_main_content": only_main_content
                },
                "ai_analysis": {
                    "enabled": ai_analysis_enabled,
                    "max_tokens": ai_max_tokens,
                    "temperature": ai_temperature,
                    "model": ai_model,
                    "fallback_enabled": fallback_enabled
                }
            }
            
            save_result = save_mcp_config(new_config)
            if save_result["success"]:
                st.success(save_result["message"])
                st.rerun()
            else:
                st.error(save_result["message"])
    
    with col2:
        if st.button("🔄 Varsayılan Ayarlara Dön", key="mcp_reset_defaults"):
            default_config = {
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
                }
            }
            
            save_result = save_mcp_config(default_config)
            if save_result["success"]:
                st.success("✅ Varsayılan ayarlar yüklendi")
                st.rerun()
            else:
                st.error(save_result["message"])
    
    with col3:
        if st.button("📖 MCP Kurulum Rehberi", key="mcp_show_guide"):
            st.info("""
            **🚀 MCP (Model Context Protocol) Kurulum Rehberi:**
            
            **1. Firecrawl MCP Server Kurulumu:**
            ```bash
            # Firecrawl MCP server'ı klonla
            git clone https://github.com/mendableai/firecrawl-mcp
            cd firecrawl-mcp
            
            # Bağımlılıkları yükle
            npm install
            
            # Server'ı başlat
            npm start
            ```
            
            **2. Konfigürasyon:**
            - MCP Etkin: ✅ İşaretle
            - Firecrawl MCP Etkin: ✅ İşaretle
            - Server URL: http://localhost:3000 (varsayılan)
            - API Key: Firecrawl API anahtarınız (opsiyonel)
            
            **3. Test:**
            - "🧪 MCP Bağlantısını Test Et" butonuna tıklayın
            - Başarılı olursa MCP ile gelişmiş scraping aktif olur
            
            **4. Avantajlar:**
            - 🔥 Firecrawl ile daha kaliteli içerik çıkarma
            - 🤖 AI ile gelişmiş hashtag ve emoji analizi
            - 📊 Daha doğru makale skorlama
            - 🎯 Hedef kitle analizi
            
            **5. Fallback:**
            - MCP başarısız olursa otomatik olarak eski yöntem kullanılır
            - Hiçbir işlevsellik kaybı olmaz
            
            **💡 Not:** MCP olmadan da uygulama tam olarak çalışır!
            """)
    
    # MCP durum özeti
    st.subheader("📊 MCP Durum Özeti")
    
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        if mcp_status["mcp_enabled"]:
            st.success("✅ MCP Aktif")
        else:
            st.error("❌ MCP Devre Dışı")
    
    with status_col2:
        if mcp_status["firecrawl_enabled"]:
            st.success("✅ Firecrawl MCP Aktif")
        else:
            st.warning("⚠️ Firecrawl MCP Devre Dışı")
    
    with status_col3:
        if mcp_status["ai_analysis_enabled"]:
            st.success("✅ AI Analizi Aktif")
        else:
            st.warning("⚠️ AI Analizi Devre Dışı")
    
    # Son güncelleme tarihi
    last_updated = mcp_config.get("last_updated", "Bilinmiyor")
    st.caption(f"Son güncelleme: {last_updated[:16] if last_updated != 'Bilinmiyor' else last_updated}")

with tab3:
    # Analiz ve raporlar sekmesi
    st.header("📊 Analiz & Raporlar")
    
    # İstatistikler
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Toplam Paylaşılan", posted_summary["total_posted"])
    with col2:
        st.metric("Son 7 Gün", posted_summary["recent_posted"])
    with col3:
        st.metric("Bekleyen Tweet", data_stats["pending_tweets"])
    
    # Detaylı istatistikler
    st.subheader("📈 Detaylı İstatistikler")
    
    stats_col1, stats_col2 = st.columns(2)
    
    with stats_col1:
        st.markdown("**📊 Veri İstatistikleri:**")
        st.write(f"• Paylaşılan Makaleler: {data_stats['posted_articles']}")
        st.write(f"• Bekleyen Tweet'ler: {data_stats['pending_tweets']}")
        st.write(f"• Paylaşılmış Tweet'ler: {data_stats['posted_tweets_in_pending']}")
        st.write(f"• Özetler: {data_stats['summaries']}")
        st.write(f"• Hashtag'ler: {data_stats['hashtags']}")
        st.write(f"• Hesaplar: {data_stats['accounts']}")
    
    with stats_col2:
        st.markdown("**⚙️ Sistem Durumu:**")
        st.write(f"• Twitter API: {'✅ Bağlı' if twitter_client else '❌ Bağlı Değil'}")
        st.write(f"• Telegram: {config_status['message'][:20]}...")
        st.write(f"• MCP: {mcp_status['message'][:20]}...")
        st.write(f"• Otomatikleştirme: {automation_status['reason'][:20]}...")
    
    # Toplu işlemler
    st.subheader("🔧 Toplu İşlemler")

    action_col1, action_col2, action_col3 = st.columns(3)
    
    with action_col1:
        if st.button("🧹 Eski Kayıtları Temizle", key="reports_clean_old"):
            with st.spinner("Eski kayıtlar temizleniyor..."):
                cleaned = check_duplicate_articles()
                st.success(f"✅ {cleaned} kayıt temizlendi")

    with action_col2:
        if st.button("📄 PDF Raporu Oluştur", key="reports_create_pdf"):
            if posted_summary["recent_articles"]:
                with st.spinner("PDF raporu oluşturuluyor..."):
                    summaries = [article.get('title', 'Tweet') for article in posted_summary["recent_articles"]]
                    pdf_path = create_pdf(summaries)
                    with open(pdf_path, "rb") as f:
                        st.download_button("📥 PDF İndir", f, file_name="tweet_raporu.pdf")
            else:
                st.warning("⚠️ Rapor için veri yok")

    with action_col3:
        if st.button("🔄 Otomatik İşlem Başlat", key="reports_auto_process"):
            st.info("🚀 Otomatik işlem başlatıldı! Terminal'de `python scheduler.py --once` çalıştırın")

# Footer
st.markdown("---")
st.markdown("🤖 **AI Tweet Bot** - Gelişmiş haber takibi ve otomatik tweet paylaşımı")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🔥 Yeni Özellikler:**")
    st.markdown("• MCP (Model Context Protocol) desteği")
    st.markdown("• Firecrawl ile gelişmiş scraping")
    st.markdown("• AI ile akıllı hashtag analizi")

with col2:
    st.markdown("**💡 İpuçları:**")
    st.markdown("• Sadece yeni haberler gösterilir")
    st.markdown("• MCP olmadan da tam çalışır")
    st.markdown("• Fallback sistemi her zaman aktif")

with col3:
    st.markdown("**🗂️ Veri Yönetimi:**")
    st.markdown("• Sidebar'dan ayarları yönetin")
    st.markdown("• MCP sekmesinden konfigürasyon")
    st.markdown("• Analiz sekmesinden raporlar")
