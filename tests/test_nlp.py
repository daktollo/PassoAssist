import pandas as pd
import joblib  # joblib is used to load models
import re
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 'konu' labels
konu_labels = [
    'cagri merkezi yetkinlik', 'diger', 'genel', 'odeme', 'uygulama',
    'iptal', 'degisiklik', 'uyelik', 'iade', 'transfer', 'fatura'
]

# Paths to the models
entity_model_path = 'data/models/entity_model.joblib'
konu_model_path = 'data/models/konu_model.joblib'   
multilabel_model_path = 'data/models/multilabel/multilabelclassifier.joblib'
sentiment_model_path = 'data/models/sentiment/saribasmetehan_sentiment_model'
severity_model_path = 'data/models/severity_classifier.joblib'

# Load models
def load_model(path):
    return joblib.load(path)

try:
    entity_model = load_model(entity_model_path)
except Exception as e:
    print(f"Error loading entity model: {e}")

try:
    konu_model = load_model(konu_model_path)
except Exception as e:
    print(f"Error loading 'konu' model: {e}")

try:
    loaded_model = load_model(severity_model_path)
    severity_model = loaded_model[0] if isinstance(loaded_model, tuple) else loaded_model
except Exception as e:
    print(f"Error loading severity model: {e}")

try:
    multilabel_model, tfidf_vectorizer = load_model(multilabel_model_path)
except Exception as e:
    print(f"Error loading multilabel model: {e}")

try:
    tokenizer = AutoTokenizer.from_pretrained(sentiment_model_path)
    sentiment_model = AutoModelForSequenceClassification.from_pretrained(sentiment_model_path)
except Exception as e:
    print(f"Error loading sentiment model: {e}")

# Functions for entity prediction
def correct_spelling(sentence):
    corrected_spellings = {
        "passolg": "passolig",
        "passolig krt": "passolig kart",
        "krt": "kart"  # Bu satırı ekleyin
    }
    words = sentence.split()
    corrected_words = [corrected_spellings.get(word.lower(), word) for word in words]
    return ' '.join(corrected_words)

def find_entities(sentence, entity_list):
    corrected_sentence = correct_spelling(sentence)
    found_entities = [entity for entity in entity_list if re.search(rf'\b{entity}(?:\w+)?\b', corrected_sentence, re.IGNORECASE)]
    return "; ".join(found_entities) if found_entities else "No entity found."

def predict_entity(input_text):
    entities = ["passo", "passolig", "passolig kart"]
    return find_entities(input_text, entities)

def predict_konu(input_text):
    predicted_label = konu_model.predict([input_text])
    return konu_labels[predicted_label[0]]

def predict_sentiment(input_text):
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True, max_length=128)
    with torch.no_grad():
        sentiment_logits = sentiment_model(**inputs).logits
        sentiment_prediction = sentiment_logits.argmax().item()
        predicted_probs = torch.softmax(sentiment_logits, dim=1)[0]

    label_mapping = {1: 'olumlu', 0: 'notr', 2: 'olumsuz'}
    sentiment_label = label_mapping[sentiment_prediction]
    sentiment_confidence = predicted_probs[sentiment_prediction].item()

    return sentiment_label, sentiment_confidence

def predict_severity(input_text):
    input_tfidf = tfidf_vectorizer.transform([input_text])
    severity_prediction = severity_model.predict(input_tfidf)[0]

    action_status = 1 if severity_prediction in [1, 2] else 0
    action_message = "Acil Harekete Geçin!" if severity_prediction == 2 else "Aksiyon Almanız Önerilir." if severity_prediction == 1 else "Harekete Geçmeye Gerek Yok."
    
    return severity_prediction, action_status, action_message

def predict_multilabel(input_text):
    input_tfidf = tfidf_vectorizer.transform([input_text])
    multilabel_prediction = multilabel_model.predict(input_tfidf)

    return {
        'bilet': multilabel_prediction[0][0],
        'musteri_hizmetleri': multilabel_prediction[0][1],
        'odeme': multilabel_prediction[0][2],
        'uygulama': multilabel_prediction[0][3],
        'passolig': multilabel_prediction[0][4],
        'passolig kart': multilabel_prediction[0][5],
        'diger': multilabel_prediction[0][6],
    }

def predict_all_models(input_text):
    entity_prediction = predict_entity(input_text)
    konu_prediction = predict_konu(input_text)
    sentiment_prediction, sentiment_confidence = predict_sentiment(input_text)
    severity_prediction, action_status, action_message = predict_severity(input_text)
    multilabel_prediction = predict_multilabel(input_text)

    return {
        'Entity': entity_prediction,
        'Konu': konu_prediction,
        'Sentiment': {
            'label': sentiment_prediction,
            'confidence': sentiment_confidence
        },
        'Severity': {
            'severity_label': severity_prediction,
            'action_status': action_status,
            'action_message': action_message
        },
        'Multilabel': multilabel_prediction
    }

# Main execution loop
if __name__ == "__main__":
    # Load existing data or create a new DataFrame
    try:
        df = pd.read_csv('user_input.csv')
    except FileNotFoundError:
        df = pd.DataFrame(columns=['text', 'entity', 'sentiment', 'konu', 'severity', 
                                   'bilet', 'musteri_hizmetleri', 'odeme', 
                                   'uygulama', 'passolig', 'passolig kart', 
                                   'diger', 'aksiyon'])

    while True:
        test_input = input("Enter text (type 'q' to quit): ")
        if test_input.lower() == 'q':
            break
        
        # Run predictions
        results = predict_all_models(test_input)

        # Show results in terminal
        print("\nPrediction Results:")
        for model, prediction in results.items():
            if model == 'Sentiment':
                print(f"{model}: {prediction['label']} (Confidence: {prediction['confidence']:.2f})")
            elif model == 'Severity':
                print(f"{model}: Severity {prediction['severity_label']}, Action Status: {prediction['action_status']} ({prediction['action_message']})")
            else:
                print(f"{model}: {prediction}")

        # Append prediction results to DataFrame
        new_row = pd.DataFrame([{
            'text': test_input,
            'entity': results['Entity'],
            'sentiment': results['Sentiment']['label'],
            'konu': results['Konu'],
            'severity': results['Severity']['severity_label'],
            'bilet': results['Multilabel']['bilet'],
            'musteri_hizmetleri': results['Multilabel']['musteri_hizmetleri'],
            'odeme': results['Multilabel']['odeme'],
            'uygulama': results['Multilabel']['uygulama'],
            'passolig': results['Multilabel']['passolig'],
            'passolig kart': results['Multilabel']['passolig kart'],
            'diger': results['Multilabel']['diger'],
            'aksiyon': results['Severity']['action_status']
        }])

        df = pd.concat([df, new_row], ignore_index=True)

        # Save DataFrame to CSV
        df.to_csv('data/test/test.csv', index=False)
        print("Prediction results saved to test_nlp.csv.")

