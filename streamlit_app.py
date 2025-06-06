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
    update_scheduler_settings, validate_automation_settings
)

load_dotenv()

# API anahtarları kontrolü
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

if not OPENROUTER_API_KEY:
    st.error("❌ OPENROUTER_API_KEY .env dosyasında bulunamadı!")
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
        if st.button("💾 Ayarları Kaydet", type="primary"):
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
        if st.button("🔄 Varsayılan Ayarlara Dön", type="secondary"):
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
    
    # Scheduler kontrol butonları
    st.header("🎮 Scheduler Kontrolü")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Otomatik Başlat", help="Otomatik haber kontrolü ve tweet oluşturma"):
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
        if st.button("⏯️ Tek Kontrol", help="Bir kez haber kontrolü yap"):
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
    if st.button("🧹 Bekleyen Tweet'leri Temizle", type="secondary"):
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
    
    if st.button("🗑️ TÜM VERİLERİ SIFIRLA", type="primary"):
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
        if st.button("❌ İptal Et"):
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

# Ana içerik alanları
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📰 Yeni Haberler")
    
    # Haber çekme butonu
    if st.button("🔄 Haberleri Yenile", type="primary"):
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
                            score = score_article(article['content'], OPENROUTER_API_KEY)
                            category = categorize_article(article['content'], OPENROUTER_API_KEY)
                            summary = summarize_article(article['content'], OPENROUTER_API_KEY)
                            
                            st.info(f"**Skor:** {score}/10 | **Kategori:** {category}")
                            st.success(f"**Özet:** {summary}")
                            
                            # Session state'e kaydet
                            article['score'] = score
                            article['category'] = category
                            article['summary'] = summary
                    
                    # Tweet oluştur butonu
                    if st.button(f"🐦 Tweet Oluştur", key=f"tweet_create_{idx}"):
                        with st.spinner("Tweet oluşturuluyor..."):
                            tweet_text = generate_ai_tweet_with_content(article, OPENROUTER_API_KEY)
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
                                    result = post_tweet(tweet_text)
                                    
                                    if result["success"]:
                                        mark_article_as_posted(article, result)
                                        st.success(f"✅ Tweet paylaşıldı! [Link]({result['url']})")
                                        
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
                        result = post_tweet(pending['tweet_text'])
                        if result["success"]:
                            mark_article_as_posted(pending['article'], result)
                            # Pending'den kaldır
                            pending['status'] = 'posted'
                            save_json("pending_tweets.json", pending_tweets)
                            st.success("✅ Tweet paylaşıldı!")
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

# Alt kısım - Toplu işlemler
st.header("🔧 Toplu İşlemler")

if st.button("🧹 Eski Kayıtları Temizle"):
    cleaned = check_duplicate_articles()
    st.success(f"✅ {cleaned} kayıt temizlendi")

if st.button("📄 PDF Raporu Oluştur"):
    if posted_summary["recent_articles"]:
        summaries = [article.get('title', 'Tweet') for article in posted_summary["recent_articles"]]
        pdf_path = create_pdf(summaries)
        with open(pdf_path, "rb") as f:
            st.download_button("📥 PDF İndir", f, file_name="tweet_raporu.pdf")
    else:
        st.warning("⚠️ Rapor için veri yok")

if st.button("🔄 Otomatik İşlem Başlat"):
    st.info("🚀 Otomatik işlem başlatıldı! Terminal'de `python scheduler.py --once` çalıştırın")

# Footer
st.markdown("---")
st.markdown("🤖 **AI Tweet Bot** - Gelişmiş haber takibi ve otomatik tweet paylaşımı")
st.markdown("💡 **İpucu:** Sadece daha önce paylaşılmamış haberler gösterilir")
st.markdown("🗂️ **Veri Yönetimi:** Sidebar'dan bekleyen tweet'leri temizleyebilir veya tüm verileri sıfırlayabilirsiniz")
