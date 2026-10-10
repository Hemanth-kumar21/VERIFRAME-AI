from __future__ import annotations


LANGUAGE_TEXT = {
    "en": {
        "simple": {
            "Likely AI": "The checks suggest this photo may be AI-generated, but the result is still an estimate.",
            "Inconclusive": "The evidence is mixed. A sharper or original file would give a more reliable answer.",
            "No AI signs found": "The checks do not show clear AI-generation signs in this image.",
        },
        "detailed": {
            "Likely AI": "The detector scores and robustness checks point toward AI-generated or altered content, but the tool does not prove it.",
            "Inconclusive": "The detector scores, quality, and provenance checks do not line up strongly enough for a clear verdict.",
            "No AI signs found": "The detector outputs and metadata checks do not show strong AI-generation indicators for this image.",
        },
    },
    "te": {
        "simple": {
            "Likely AI": "చెకలు చూస్తే ఈ ఫోటో AIతో తయారైంది అనిపిస్తుంది, కానీ ఇది ఖచ్చితమైన నిర్ధారణ కాదు.",
            "Inconclusive": "సాక్ష్యాలు మిశ్రమంగా ఉన్నాయి. మెరుగైన అసలు ఫైల్ ఉంటే సరైన సమాధానం లభిస్తుంది.",
            "No AI signs found": "ఈ ఇమేజ్‌లో AI జనరేషన్ గుర్తులు స్పష్టంగా కనిపించలేదు.",
        },
        "detailed": {
            "Likely AI": "డిటెక్టర్ స్కోర్లు మరియు మూల్యాంకనాలు ఈ ఫోటో AIతో తయారైనది లేదా మార్చబడినది అని సూచిస్తున్నాయి, కానీ ఇది నిరూపణ కాదు.",
            "Inconclusive": "డిటెక్టర్ స్కోర్లు, నాణ్యత మరియు మూల సమాచారంతో సరిపోలేదనే కారణంగా స్పష్టమైన నిర్ణయం ఇవ్వలేకపోయాం.",
            "No AI signs found": "డిటెక్టర్ నిర్ణయాలు మరియు మెటాడేటా పరీక్షలు ఈ ఇమేజ్‌లో AI సంకేతాలను బలంగా చూపించలేదు.",
        },
    },
    "hi": {
        "simple": {
            "Likely AI": "जाँच से लगता है कि यह फोटो AI से बनाया गया हो सकता है, लेकिन यह निश्चित प्रमाण नहीं है।",
            "Inconclusive": "सबूत मिलाजुला हैं। मूल या स्पष्ट फाइल मिलने पर परिणाम अधिक भरोसेमंद होगा।",
            "No AI signs found": "इस फोटो में AI-जेनरेशन के स्पष्ट संकेत नहीं दिखते।",
        },
        "detailed": {
            "Likely AI": "डिटेक्टर स्कोर और ताकत की जाँच इस बात की ओर इशारा करती है कि फोटो AI से बनाया गया या बदला गया है, लेकिन यह प्रमाण नहीं है।",
            "Inconclusive": "डिटेक्टर, क्वालिटी और प्रॉवेनेन्स चेक एक साफ़ निर्णय के लिए पर्याप्त रूप से मेल नहीं खाते हैं।",
            "No AI signs found": "डिटेक्टर आउटपुट और मेटाडेटा जाँच इस image में AI संकेतों को मजबूत तरीके से नहीं दिखाती हैं।",
        },
    },
}


def build_explanation(verdict: str, lang: str = "en", style: str = "simple") -> str:
    lang_key = LANGUAGE_TEXT.get(lang, LANGUAGE_TEXT["en"])
    style_key = lang_key.get(style, lang_key["simple"])
    return style_key.get(verdict, style_key["Inconclusive"])
