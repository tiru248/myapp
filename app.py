from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Render Flask App is Working!"

if __name__ == "__main__":
    from flask import Flask
    app.run(host="0.0.0.0", port=5000)

