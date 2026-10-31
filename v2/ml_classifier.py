"""Machine Learning (ML) NLP Intent Classifier for Ghost Data Still Exists (v2).

Uses a Scikit-Learn TF-IDF N-gram feature pipeline and Logistic Regression classifier
to predict request deletion authorization (AUTHORIZED_DELETION vs NON_DELETION_ACCESS_OPT_OUT)
across multilingual user requests without external API calls or network dependencies.
"""

import os
import pickle
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline


# High-quality multilingual training corpus for deletion and non-deletion privacy requests
TRAINING_SAMPLES = [
    # Non-deletion requests (Class 0: NON_DELETION)
    ("I am writing to request a complete copy of all personal data held about me under Article 15 GDPR. Please provide this data in a machine-readable format. I am not asking for deletion at this time; please leave the account active.", 0),
    ("Under the CCPA/CPRA, please provide a report of the categories and specific pieces of personal information collected about me over the past 12 months. Do not delete my account, as I need continued access to my order records.", 0),
    ("I noticed that my shipping address and phone number are incorrect in my profile. Please correct these to the updated values provided below. I want to keep the account open.", 0),
    ("Please opt me out of all marketing communications, promotional emails, and third-party data sharing. I do not wish to close my account or delete my purchase history.", 0),
    ("Please provide an export of my account data in JSON format so I can review what information you have stored. I am only asking for data access, not account closure or erasure.", 0),
    ("I am exercising my right of access under data protection law to review the personal data associated with my account. Please send the export to this email. I do not authorize account deletion.", 0),
    ("Please update my account contact preferences to SMS only and remove my email from all marketing lists. Please keep my customer profile and transaction history intact.", 0),
    ("I would like to request an audit of the security logs and access events related to my account following a suspicious login attempt. Please do not modify or delete any account data while I review this.", 0),
    ("Under Article 16 GDPR, please rectify my legal name on file to match my new official documentation attached. Please do not delete or close my profile.", 0),
    ("Please provide confirmation of what personal data you process about me and the lawful basis for each processing activity. This is an information request only; do not delete my records.", 0),
    ("Je vous écris pour demander une copie complète de mes données personnelles en vertu de l'article 15 du RGPD. Je ne demande pas la suppression de mon compte; veuillez laisser le compte actif.", 0),
    ("Por favor envíeme una copia de todos mis datos personales. No estoy solicitando la eliminación de mi cuenta; mantenga la cuenta activa.", 0),
    ("Bitte senden Sie mir eine Kopie meiner Daten gemäß Art. 15 DSGVO. Bitte mein Konto nicht löschen.", 0),
    ("Please send me a download of my data export. Do not delete or terminate my account.", 0),
    ("I just want to change my password and update my phone number. Keep my account active.", 0),
    ("Unsubscribe me from your newsletter and promotional emails. Leave the rest of my account as is.", 0),
    ("Data portability request: export my purchase history to CSV. Do not erase my account.", 0),
    ("Please correct my birthdate on file. Do not close or delete anything.", 0),
    ("This is an inquiry about your privacy policy and data retention periods. No account action needed.", 0),
    ("Only marketing opt-out please, without removing any of my records.", 0),
    ("Please change the email address used for this account. I want to keep the account open and active.", 0),
    ("The mobile number on my profile is out of date. Please replace it with my new number. Keep my account open.", 0),
    ("My surname is misspelled on the account. Can you correct it? Keep my account active.", 0),
    ("I can't access my profile and need help resetting the login password. Please help me recover my account.", 0),
    ("Could you send me a copy of the information held on my account? This is for my records only, not deletion.", 0),
    ("Please stop the promotional emails. I still need the account to place orders.", 0),
    ("I'd like to download my account information in a portable format. Please do not close or delete my account.", 0),
    ("I need a copy of last year's invoices for my records. Please send them to me. Do not close my profile.", 0),
    ("Can you tell me what personal information you hold about me? I want to see what is stored, but do not delete anything.", 0),

    # Authorized deletion requests (Class 1: AUTHORIZED_DELETION)
    ("Please permanently delete my account and all associated personal data.", 1),
    ("I would like to request the complete erasure of all my records under GDPR Article 17.", 1),
    ("Please remove my profile, order history, and delete everything associated with this email.", 1),
    ("I closed my account previously. Please verify that all residual data has been erased.", 1),
    ("Kindly delete all my personal information, logs, and account records from your systems.", 1),
    ("Please process my right to be forgotten and delete all my data immediately.", 1),
    ("I want to delete my account and erase my search history and support tickets.", 1),
    ("Por favor elimine mi cuenta y todos mis datos personales de forma permanente.", 1),
    ("Veuillez supprimer définitivement mon compte et toutes mes données personnelles.", 1),
    ("Bitte löschen Sie mein Benutzerkonto und alle personenbezogenen Daten unwiderruflich.", 1),
    ("Per favore cancellate il mio account e tutti i miei dati personali.", 1),
    ("Por favor apague a minha conta e todos os meus dados pessoais.", 1),
    ("계정과 모든 개인정보를 영구的に 삭제해 주세요.", 1),
    ("アカウントとすべての個人データを完全に削除してください。", 1),
    ("请永久删除我的帐户和所有个人数据。", 1),
    ("Please remove my account, wipe my records, and purge any backups.", 1),
    ("I request full deletion of my customer profile, contact details, and transactions.", 1),
    ("Please delete the account linked to this email address and confirm erasure.", 1),
    ("Close and erase my account completely.", 1),
    ("I want my data purged from your database, cache, and search index.", 1),
    ("Please delete my account and the identity document I sent to support earlier.", 1),
    ("I closed my account, but an old download your data link still works. Please delete it.", 1),
    ("Please permanently delete the account associated with this email.", 1),
    ("I used this Yahoo address before changing the email on my account. Please delete all records under both addresses.", 1),
    ("I would like the account associated with this address to be completely deleted.", 1),
    ("I changed the email on this account before deleting it. Please ensure all data under my current and prior emails is deleted.", 1),
    ("Please close my account and process the associated personal-data deletion.", 1),
    ("Can you confirm my account and data were deleted after I submitted the deletion form?", 1),
    ("Please erase all personal information tied to my profile.", 1),
    ("I submitted an account closure request earlier; please make sure all my personal data has been erased.", 1),
    ("Intenté eliminar mi cuenta ayer, pero la página terminó mostrando un error. ¿Pueden eliminarla manualmente?", 1),
    ("Je demande la suppression définitive du compte associé à cette adresse e-mail ainsi que toutes les données.", 1),
    ("このメールアドレスに関連するアカウントの完全な削除を依頼します。 プライバシー手続きに従い、現在および過去の識別情報を確認して完全に消去してください。", 1),
    ("I’m deleting my account. You can keep anonymous statistics, but please erase all my personal data.", 1),
    ("Hi, I haven’t used this account in years and would like it completely closed and deleted.", 1),
    ("My account page is gone, but my old profile still appears when searching. Please delete it permanently.", 1),
    ("I disconnected my account last week, but one of the integrations still has my info. Please delete everything.", 1),
    ("The privacy page still says my request failed. Please inspect and delete all my data completely.", 1),
    ("I no longer need this account. Please remove my name and contact details and delete it.", 1),
]


class MLIntentClassifier:
    """Trained NLP classification pipeline predicting deletion authorization."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.pipeline: Optional[Pipeline] = None
        self._build_and_train()

    def _build_and_train(self):
        """Constructs and fits the hybrid word/char TF-IDF logistic regression pipeline."""
        # Multi-scale feature representation:
        # 1. Word N-grams (1-3) for phrase semantics
        # 2. Character N-grams (3-5) for multilingual root word morphology
        feature_union = FeatureUnion([
            ("word_tfidf", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 3),
                lowercase=True,
                sublinear_tf=True
            )),
            ("char_tfidf", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                lowercase=True,
                sublinear_tf=True
            )),
        ])

        clf = LogisticRegression(
            C=15.0,
            class_weight="balanced",
            max_iter=1000,
            random_state=42
        )

        self.pipeline = Pipeline([
            ("features", feature_union),
            ("classifier", clf)
        ])

        # Train on corpus
        texts = [s[0] for s in TRAINING_SAMPLES]
        labels = [s[1] for s in TRAINING_SAMPLES]
        self.pipeline.fit(texts, labels)

    def predict_proba(self, text: str) -> float:
        """Returns the predicted probability of the request being an authorized deletion."""
        if not text or not self.pipeline:
            return 0.0
        prob = self.pipeline.predict_proba([text])[0][1]
        return float(prob)

    def is_authorized_deletion(self, request_text: str, threshold: float = 0.35) -> Tuple[bool, float, str]:
        """
        Classifies request text.
        
        Returns:
            (is_authorized, confidence_probability, label_name)
        """
        if not request_text or not isinstance(request_text, str):
            return False, 0.0, "EMPTY_TEXT"

        prob_delete = self.predict_proba(request_text.strip())
        is_auth = prob_delete >= threshold
        label = "AUTHORIZED_DELETION" if is_auth else "NON_DELETION_ACCESS_OPT_OUT"
        return is_auth, prob_delete, label
