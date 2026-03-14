from flask import Flask, request, render_template
import torch
import torch.nn as nn
from transformers import BertTokenizer, BertModel
import joblib
import numpy as np
import traceback
import os

# Heuristic extraction script ko import kar rahe hain
from heuristics.feature_extraction import extract_all_features

app = Flask(__name__)

# --- Configuration ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
MODEL_PATH = 'phishai_model.pth' 
SCALER_PATH = 'scaler.pkl'       
MAX_LEN = 128                    

# --- Load Assets ---
try:
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    scaler = None
    for name in [SCALER_PATH, 'scaler.pkl', 'scaler.pkl']:
        if os.path.exists(name):
            scaler = joblib.load(name)
            print(f"✅ Scaler loaded: {name}")
            break
except Exception as e:
    print(f"⚠️ Initialization Error: {e}")

# --- Model Architecture ---
class PhiShAI(nn.Module):
    def __init__(self, feat_dim):
        super().__init__()
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        # Fine-tuning: Last 2 layers unfreeze
        for name, param in self.bert.named_parameters():
            if 'encoder.layer.10' in name or 'encoder.layer.11' in name:
                param.requires_grad = True
            else:
                param.requires_grad = False
        self.fc = nn.Sequential(
            nn.Linear(768 + feat_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 2)
        )

    def forward(self, ids, mask, feats):
        outs = self.bert(ids, attention_mask=mask)
        cls = outs.last_hidden_state[:, 0, :]
        comb = torch.cat((cls, feats), dim=1)
        return self.fc(comb)

# --- Initialize Model ---
phish_model = None
if scaler is not None:
    feat_dim = scaler.n_features_in_
    if os.path.exists(MODEL_PATH):
        phish_model = PhiShAI(feat_dim).to(DEVICE)
        phish_model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
        phish_model.eval()
        print(f"✅ Model weights loaded successfully.")

# --- Logic Layer ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        if not text:
            return render_template('index.html', error="Please paste a message!")

        try:
            # 1. Feature Extraction & Scaling
            raw_feats = extract_all_features(text)
            heuristic_val = int(sum(raw_feats))
            scaled = scaler.transform(np.array([raw_feats], dtype=np.float32))
            feats_tensor = torch.from_numpy(scaled).float().to(DEVICE)

            # 2. BERT Tokenization
            enc = tokenizer(text, truncation=True, padding='max_length', max_length=MAX_LEN, return_tensors='pt')
            ids, mask = enc['input_ids'].to(DEVICE), enc['attention_mask'].to(DEVICE)

            # 3. Model Inference
            with torch.no_grad():
                output = phish_model(ids, mask, feats_tensor)
                probs = torch.softmax(output, dim=1)
                phish_prob = probs[0][1].item()

            # --- 🛠️ STEP 3: HYBRID INTELLIGENCE LOGIC ---
            text_lower = text.lower()
            
            # A. Phishing Markers (Danger Signals)
            danger_words = ['urgent', 'unauthorized', 'restricted', 'action required', 'suspended', 'verify now']
            triggered_danger = sum(1 for w in danger_words if w in text_lower)
            
            # B. Legit Markers (Safe Signals for Spotify/Netflix cases)
            safe_patterns = ['no action needed', 'thanks for listening', 'set to renew', 'receipt', 'invoice']
            is_informational = any(p in text_lower for p in safe_patterns)

            # --- FINAL DECISION ---
            is_phish = False
            
            # Case 1: High Confidence AI (Strong Signal)
            if phish_prob > 0.80:
                is_phish = True
            
            # Case 2: Moderate AI + High Heuristics + Link (Structural Signal)
            elif phish_prob > 0.4 and heuristic_val > 5 and "http" in text_lower:
                is_phish = True
            
            # Case 3: Pattern Match (Social Engineering Signal like PayPal)
            elif triggered_danger >= 1 and "http" in text_lower and phish_prob > 0.5:
                is_phish = True

            # --- SAFETY OVERRIDE (For False Positives) ---
            # Agar message informational hai aur koi "urgent" word nahi hai, force to SAFE
            if is_informational and triggered_danger == 0:
                is_phish = False
                phish_prob = min(phish_prob, 0.25) # Probability score kam kar do UI ke liye

            # Result Formatting
            if is_phish:
                verdict, css_class = "Phishing Attempt Detected", "phishing"
            else:
                verdict, css_class = "Message Appears Safe", "safe"

            return render_template('result.html', 
                                   result=verdict, 
                                   status_class=css_class,
                                   bert_score=f"{phish_prob*100:.1f}%",
                                   heuristic_score=str(heuristic_val),
                                   total_features=str(scaler.n_features_in_),
                                   ai_prob="Active (Hybrid Logic)")

        except Exception as e:
            traceback.print_exc()
            return render_template('index.html', error=f"Analysis error: {str(e)}")

    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)