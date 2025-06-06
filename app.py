
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Streamlit uygulaması ayrı çalışıyor. Bu sadece ana kontrol noktasıdır."
