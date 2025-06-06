import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from utils import (
    fetch_latest_ai_articles, summarize_article, score_article,
    categorize_article, generate_ai_tweet_with_content, create_pdf,
    load_json, save_json, post_tweet, mark_article_as_posted,
    check_duplicate_articles, setup_twitter_api
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
    
    # Otomatik/Manuel mod
    auto_mode = st.checkbox("🔄 Otomatik Tweet Paylaşımı", value=False)
    
    # Minimum skor ayarı
    min_score = st.slider("📊 Minimum Makale Skoru", 1, 10, 6)
    
    # İstatistikler
    st.header("📈 İstatistikler")
    posted_articles = load_json("posted_articles.json")
    pending_tweets = load_json("pending_tweets.json")
    
    st.metric("Paylaşılan Tweet", len(posted_articles))
    st.metric("Bekleyen Tweet", len([t for t in pending_tweets if t.get("status") == "pending"]))

# Ana içerik alanları
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📰 Yeni Haberler")
    
    # Haber çekme butonu
    if st.button("🔄 Haberleri Yenile", type="primary"):
        with st.spinner("Haberler çekiliyor..."):
            # Tekrarlanan makaleleri temizle
            cleaned_count = check_duplicate_articles()
            if cleaned_count > 0:
                st.info(f"🧹 {cleaned_count} eski makale temizlendi")
            
            articles = fetch_latest_ai_articles()
            st.session_state.articles = articles
            
            if articles:
                st.success(f"✅ {len(articles)} yeni makale bulundu!")
            else:
                st.warning("⚠️ Yeni makale bulunamadı")

    # Makaleleri göster
    if 'articles' in st.session_state and st.session_state.articles:
        for idx, article in enumerate(st.session_state.articles):
            with st.expander(f"📝 {article['title'][:80]}..."):
                st.markdown(f"**🔗 URL:** {article['url']}")
                
                # İçerik önizlemesi
                if article.get('content'):
                    st.markdown(f"**📄 İçerik Önizlemesi:**")
                    st.text(article['content'][:300] + "..." if len(article['content']) > 300 else article['content'])
                
                # Ana butonlar
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
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
                
                with col_b:
                    if st.button(f"🐦 Tweet Oluştur", key=f"tweet_{idx}"):
                        with st.spinner("Tweet oluşturuluyor..."):
                            tweet_text = generate_ai_tweet_with_content(article, OPENROUTER_API_KEY)
                            st.session_state[f'tweet_{idx}'] = tweet_text
                            st.success("✅ Tweet oluşturuldu!")
                
                with col_c:
                    if st.button(f"💾 Kaydet", key=f"save_{idx}"):
                        # Tweet varsa kaydet
                        if f'tweet_{idx}' in st.session_state:
                            tweet_text = st.session_state[f'tweet_{idx}']
                        else:
                            tweet_text = generate_ai_tweet_with_content(article, OPENROUTER_API_KEY)
                        
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
                
                # Tweet göster ve paylaş (ayrı satırda)
                if f'tweet_{idx}' in st.session_state:
                    tweet_text = st.session_state[f'tweet_{idx}']
                    
                    st.markdown("**🐦 Oluşturulan Tweet:**")
                    st.text_area("Tweet İçeriği", tweet_text, height=100, key=f"display_{idx}", label_visibility="collapsed")
                    
                    # Skor kontrolü
                    article_score = article.get('score', 0)
                    if article_score < min_score:
                        st.warning(f"⚠️ Düşük skor ({article_score}). Minimum: {min_score}")
                    
                    # Paylaşım butonları (ayrı satırda)
                    share_col1, share_col2 = st.columns(2)
                    
                    with share_col1:
                        if st.button(f"📤 Tweet Paylaş", key=f"share_{idx}", disabled=not twitter_client):
                            if twitter_client:
                                with st.spinner("Tweet paylaşılıyor..."):
                                    result = post_tweet(tweet_text)
                                    
                                    if result["success"]:
                                        mark_article_as_posted(article, result)
                                        st.success(f"✅ Tweet paylaşıldı! [Link]({result['url']})")
                                        
                                        # Session state'den kaldır
                                        if f'tweet_{idx}' in st.session_state:
                                            del st.session_state[f'tweet_{idx}']
                                    else:
                                        st.error(f"❌ Hata: {result['error']}")
                            else:
                                st.error("❌ Twitter API bağlantısı yok")
                    
                    with share_col2:
                        if st.button(f"✏️ Düzenle", key=f"edit_{idx}"):
                            st.session_state[f'editing_{idx}'] = True
                
                # Düzenleme modu
                if st.session_state.get(f'editing_{idx}', False):
                    current_tweet = st.session_state.get(f'tweet_{idx}', '')
                    new_tweet = st.text_area("Yeni Tweet:", current_tweet, key=f"edit_text_{idx}")
                    
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        if st.button(f"💾 Kaydet", key=f"save_edit_{idx}"):
                            st.session_state[f'tweet_{idx}'] = new_tweet
                            st.session_state[f'editing_{idx}'] = False
                            st.success("💾 Değişiklikler kaydedildi!")
                            st.rerun()
                    
                    with edit_col2:
                        if st.button(f"❌ İptal", key=f"cancel_edit_{idx}"):
                            st.session_state[f'editing_{idx}'] = False
                            st.rerun()

with col2:
    st.header("⏳ Bekleyen Tweet'ler")
    
    # Bekleyen tweet'leri göster
    pending_tweets = load_json("pending_tweets.json")
    pending_list = [t for t in pending_tweets if t.get("status") == "pending"]
    
    if pending_list:
        for idx, pending in enumerate(pending_list):
            with st.expander(f"📝 {pending['article']['title'][:40]}..."):
                st.markdown(f"**Skor:** {pending.get('score', 'N/A')}/10")
                st.markdown(f"**Tarih:** {pending.get('created_date', '')[:16]}")
                
                st.text_area("Tweet İçeriği:", pending['tweet_text'], height=80, key=f"pending_{idx}", label_visibility="collapsed")
                
                col_p1, col_p2, col_p3 = st.columns(3)
                
                with col_p1:
                    if st.button(f"✅ Onayla", key=f"approve_{idx}"):
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
                
                with col_p2:
                    if st.button(f"❌ Reddet", key=f"reject_{idx}"):
                        pending['status'] = 'rejected'
                        save_json("pending_tweets.json", pending_tweets)
                        st.info("❌ Tweet reddedildi")
                        st.rerun()
                
                with col_p3:
                    if st.button(f"✏️ Düzenle", key=f"edit_pending_{idx}"):
                        st.session_state[f'editing_pending_{idx}'] = True
                
                # Düzenleme modu
                if st.session_state.get(f'editing_pending_{idx}', False):
                    new_tweet = st.text_area("Yeni Tweet:", pending['tweet_text'], key=f"edit_pending_text_{idx}")
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        if st.button(f"💾 Kaydet", key=f"save_pending_edit_{idx}"):
                            pending['tweet_text'] = new_tweet
                            save_json("pending_tweets.json", pending_tweets)
                            st.session_state[f'editing_pending_{idx}'] = False
                            st.success("💾 Değişiklikler kaydedildi!")
                            st.rerun()
                    
                    with col_e2:
                        if st.button(f"❌ İptal", key=f"cancel_pending_edit_{idx}"):
                            st.session_state[f'editing_pending_{idx}'] = False
                            st.rerun()
    else:
        st.info("📭 Bekleyen tweet yok")
    
    # Geçmiş tweet'ler
    st.header("📜 Paylaşılan Tweet'ler")
    
    if posted_articles:
        for article in posted_articles[-5:]:  # Son 5 tweet
            with st.expander(f"✅ {article.get('title', 'Tweet')[:30]}..."):
                st.markdown(f"**Tarih:** {article.get('posted_date', '')[:16]}")
                if article.get('tweet_url'):
                    st.markdown(f"**Link:** [Tweet'i Görüntüle]({article['tweet_url']})")
                st.markdown(f"**URL:** {article.get('url', 'N/A')}")
    else:
        st.info("📭 Henüz paylaşılan tweet yok")

# Alt kısım - Toplu işlemler
st.header("🔧 Toplu İşlemler")

col_bulk1, col_bulk2, col_bulk3 = st.columns(3)

with col_bulk1:
    if st.button("🧹 Eski Kayıtları Temizle"):
        cleaned = check_duplicate_articles()
        st.success(f"✅ {cleaned} kayıt temizlendi")

with col_bulk2:
    if st.button("📄 PDF Raporu Oluştur"):
        if posted_articles:
            summaries = [article.get('title', 'Tweet') for article in posted_articles]
            pdf_path = create_pdf(summaries)
            with open(pdf_path, "rb") as f:
                st.download_button("📥 PDF İndir", f, file_name="tweet_raporu.pdf")
        else:
            st.warning("⚠️ Rapor için veri yok")

with col_bulk3:
    if st.button("🔄 Otomatik İşlem Başlat"):
        st.info("🚀 Otomatik işlem başlatıldı! Terminal'de `python scheduler.py --once` çalıştırın")

# Footer
st.markdown("---")
st.markdown("🤖 **AI Tweet Bot** - Gelişmiş haber takibi ve otomatik tweet paylaşımı")
