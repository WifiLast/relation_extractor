"""
Subjectivity and sentiment/emotion analysis for text.

Combines a fast, explainable POS/lexicon heuristic (always available) with
NLTK's VADER sentiment analyzer for emotion detection, and an optional
Naive Bayes classifier trained on NLTK's subjectivity corpus for a second
opinion (lazily trained on first use, best-effort).
"""
import re

import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.tag import pos_tag

try:
    from spacy_relation_extract import split_into_sentences
except Exception:
    def split_into_sentences(text):
        return sent_tokenize(text)


# ---------------------------------------------------------------------------
# NLTK resource bootstrap
# ---------------------------------------------------------------------------
def _ensure_nltk_resource(find_path, download_name):
    try:
        nltk.data.find(find_path)
    except LookupError:
        nltk.download(download_name)


_ensure_nltk_resource('sentiment/vader_lexicon.zip', 'vader_lexicon')


# ---------------------------------------------------------------------------
# Lexicons used for the heuristic subjectivity score
# ---------------------------------------------------------------------------
FIRST_PERSON = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves"}
SECOND_PERSON = {"you", "your", "yours", "yourself", "yourselves"}
THIRD_PERSON = {"he", "him", "his", "she", "her", "hers", "it", "its", "they", "them", "their", "theirs"}

SUBJECTIVE_VERBS = {
    "think", "thinks", "thought", "believe", "believes", "believed", "feel", "feels", "felt",
    "guess", "guesses", "suppose", "supposes", "assume", "assumes", "doubt", "doubts",
    "wonder", "wonders", "hope", "hopes", "wish", "wishes", "love", "loves", "loved",
    "hate", "hates", "hated", "prefer", "prefers", "like", "likes", "liked", "dislike",
    "dislikes", "adore", "adores", "despise", "despises", "regret", "regrets", "fear",
    "fears", "worry", "worries", "suspect", "suspects", "reckon", "imagine", "imagines",
}

EVALUATIVE_WORDS = {
    "good", "bad", "great", "terrible", "awful", "amazing", "wonderful", "horrible",
    "best", "worst", "favorite", "favourite", "beautiful", "ugly", "excellent", "poor",
    "fantastic", "disgusting", "incredible", "outrageous", "ridiculous", "brilliant",
    "awesome", "disappointing", "impressive", "shocking", "unbelievable", "lovely",
    "nasty", "pathetic", "stunning", "magnificent",
}

INTENSIFIERS = {
    "very", "extremely", "absolutely", "totally", "really", "so", "such", "utterly",
    "completely", "highly", "incredibly", "remarkably", "quite", "rather", "too",
}

HEDGES = {
    "maybe", "perhaps", "possibly", "probably", "likely", "seems", "seemingly",
    "appears", "apparently", "allegedly", "reportedly", "supposedly", "arguably",
}

REPORTING_VERBS = {
    "said", "states", "stated", "reports", "reported", "announces", "announced",
    "publishes", "published", "confirms", "confirmed", "notes", "noted", "found",
    "measures", "measured", "records", "recorded", "observes", "observed",
    "according",
}

ADJECTIVE_TAGS = {"JJ", "JJR", "JJS"}
ADVERB_TAGS = {"RB", "RBR", "RBS"}
NUMBER_TAGS = {"CD"}
PROPER_NOUN_TAGS = {"NNP", "NNPS"}
MODAL_TAG = "MD"


def _tokenize_and_tag(sentence):
    tokens = word_tokenize(sentence)
    return tokens, pos_tag(tokens)


def compute_subjective_cues(sentence):
    """
    Count POS/lexicon-based cues that indicate subjective vs. objective language.
    :param sentence: A single sentence (str).
    :return: dict of raw counts plus a normalized 0-1 lexical subjectivity score.
    """
    tokens, tagged = _tokenize_and_tag(sentence)
    lower_tokens = [t.lower() for t in tokens]
    total_tokens = max(1, len(tokens))

    counts = {
        "adjectives": 0,
        "adverbs": 0,
        "modals": 0,
        "first_person_pronouns": 0,
        "second_person_pronouns": 0,
        "third_person_pronouns": 0,
        "subjective_verbs": 0,
        "evaluative_words": 0,
        "intensifiers": 0,
        "hedges": 0,
        "reporting_verbs": 0,
        "numbers": 0,
        "proper_nouns": 0,
        "exclamations": sentence.count("!"),
        "all_caps_words": sum(
            1 for t in tokens if len(t) > 1 and t.isupper() and t.isalpha()
        ),
    }

    for word, tag in tagged:
        w = word.lower()
        if tag in ADJECTIVE_TAGS:
            counts["adjectives"] += 1
        if tag in ADVERB_TAGS:
            counts["adverbs"] += 1
        if tag == MODAL_TAG:
            counts["modals"] += 1
        if tag in NUMBER_TAGS:
            counts["numbers"] += 1
        if tag in PROPER_NOUN_TAGS:
            counts["proper_nouns"] += 1
        if w in FIRST_PERSON:
            counts["first_person_pronouns"] += 1
        if w in SECOND_PERSON:
            counts["second_person_pronouns"] += 1
        if w in THIRD_PERSON:
            counts["third_person_pronouns"] += 1
        if w in SUBJECTIVE_VERBS:
            counts["subjective_verbs"] += 1
        if w in EVALUATIVE_WORDS:
            counts["evaluative_words"] += 1
        if w in INTENSIFIERS:
            counts["intensifiers"] += 1
        if w in HEDGES:
            counts["hedges"] += 1
        if w in REPORTING_VERBS:
            counts["reporting_verbs"] += 1

    subjective_hits = (
        counts["adjectives"] * 1.0
        + counts["adverbs"] * 0.5
        + counts["modals"] * 0.5
        + counts["first_person_pronouns"] * 1.0
        + counts["second_person_pronouns"] * 0.5
        + counts["subjective_verbs"] * 1.5
        + counts["evaluative_words"] * 1.5
        + counts["intensifiers"] * 1.0
        + counts["hedges"] * 0.5
        + counts["exclamations"] * 1.0
        + counts["all_caps_words"] * 0.5
    )
    objective_hits = (
        counts["numbers"] * 1.0
        + counts["proper_nouns"] * 0.3
        + counts["reporting_verbs"] * 1.0
        + counts["third_person_pronouns"] * 0.3
    )

    lexical_ratio = subjective_hits / (subjective_hits + objective_hits + 1.0)
    density = min(1.0, (subjective_hits / total_tokens) * 4.0)

    counts["subjective_hits"] = round(subjective_hits, 2)
    counts["objective_hits"] = round(objective_hits, 2)
    counts["lexical_subjectivity_ratio"] = round(lexical_ratio, 3)
    counts["subjective_density"] = round(density, 3)
    return counts


# ---------------------------------------------------------------------------
# Sentiment / emotion via VADER
# ---------------------------------------------------------------------------
_SENTIMENT_ANALYZER = None


def get_sentiment_analyzer():
    global _SENTIMENT_ANALYZER
    if _SENTIMENT_ANALYZER is None:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        _SENTIMENT_ANALYZER = SentimentIntensityAnalyzer()
    return _SENTIMENT_ANALYZER


def _emotion_label(compound):
    if compound >= 0.5:
        return "strongly positive"
    if compound >= 0.05:
        return "mildly positive"
    if compound <= -0.5:
        return "strongly negative"
    if compound <= -0.05:
        return "mildly negative"
    return "neutral"


def _emotion_intensity(compound):
    magnitude = abs(compound)
    if magnitude < 0.05:
        return "none"
    if magnitude < 0.3:
        return "low"
    if magnitude < 0.6:
        return "moderate"
    return "high"


def analyze_emotion(text):
    """
    Run VADER sentiment analysis and translate it into an emotion summary.
    :param text: Input text (sentence or full document).
    :return: dict with polarity scores, emotion label, intensity and a boolean flag.
    """
    analyzer = get_sentiment_analyzer()
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]
    intensity = _emotion_intensity(compound)
    return {
        "polarity": scores,
        "emotion_label": _emotion_label(compound),
        "emotional_intensity": intensity,
        "is_emotional": intensity != "none",
    }


# ---------------------------------------------------------------------------
# Optional ML classifier trained on NLTK's subjectivity corpus (best effort)
# ---------------------------------------------------------------------------
_ML_CLASSIFIER_STATE = None
_ML_CLASSIFIER_UNAVAILABLE = False


def _train_subjectivity_classifier(n_instances=1000):
    from nltk.corpus import subjectivity
    from nltk.classify import NaiveBayesClassifier
    from nltk.sentiment import SentimentAnalyzer
    from nltk.sentiment.util import extract_unigram_feats, mark_negation

    subj_docs = [(sent, "subj") for sent in subjectivity.sents(categories="subj")[:n_instances]]
    obj_docs = [(sent, "obj") for sent in subjectivity.sents(categories="obj")[:n_instances]]

    split = int(n_instances * 0.8)
    train_docs = subj_docs[:split] + obj_docs[:split]
    test_docs = subj_docs[split:] + obj_docs[split:]

    analyzer = SentimentAnalyzer()
    all_words_neg = analyzer.all_words([mark_negation(doc) for doc in train_docs])
    unigram_feats = analyzer.unigram_word_feats(all_words_neg, min_freq=4)
    analyzer.add_feat_extractor(extract_unigram_feats, unigrams=unigram_feats)

    training_set = analyzer.apply_features(train_docs)
    test_set = analyzer.apply_features(test_docs)
    classifier = analyzer.train(NaiveBayesClassifier.train, training_set)
    accuracy = nltk.classify.accuracy(classifier, test_set)

    return analyzer, classifier, accuracy


def get_ml_subjectivity_classifier():
    """Lazily train (once) and cache the subjectivity-corpus classifier. Returns None on failure."""
    global _ML_CLASSIFIER_STATE, _ML_CLASSIFIER_UNAVAILABLE
    if _ML_CLASSIFIER_UNAVAILABLE:
        return None
    if _ML_CLASSIFIER_STATE is not None:
        return _ML_CLASSIFIER_STATE
    try:
        _ensure_nltk_resource("corpora/subjectivity.zip", "subjectivity")
        _ML_CLASSIFIER_STATE = _train_subjectivity_classifier()
        return _ML_CLASSIFIER_STATE
    except Exception as e:
        print(f"Subjectivity ML classifier unavailable, falling back to heuristic only: {e}")
        _ML_CLASSIFIER_UNAVAILABLE = True
        return None


def classify_subjectivity_ml(sentence):
    """Best-effort ML subjectivity classification. Returns None if the classifier can't be used."""
    state = get_ml_subjectivity_classifier()
    if state is None:
        return None
    try:
        analyzer, classifier, accuracy = state
        tokens = word_tokenize(sentence.lower())
        featureset = analyzer.extract_features(tokens)
        label = classifier.classify(featureset)
        try:
            prob_dist = classifier.prob_classify(featureset)
            confidence = prob_dist.prob(label)
        except Exception:
            confidence = None
        return {
            "label": "subjective" if label == "subj" else "objective",
            "confidence": round(confidence, 3) if confidence is not None else None,
            "classifier_test_accuracy": round(accuracy, 3),
        }
    except Exception as e:
        print(f"Error running ML subjectivity classifier: {e}")
        return None


# ---------------------------------------------------------------------------
# Combined heuristic subjectivity score
# ---------------------------------------------------------------------------
def _subjectivity_label(score):
    if score < 0.35:
        return "objective"
    if score < 0.6:
        return "mixed"
    return "subjective"


def analyze_sentence(sentence, use_ml_classifier=False):
    """
    Analyze a single sentence for subjectivity and emotion.
    :param sentence: Sentence text.
    :param use_ml_classifier: If True, also run the (slower, best-effort) ML classifier.
    :return: dict with subjectivity score/label, cue counts, emotion info, and optional ML result.
    """
    cues = compute_subjective_cues(sentence)
    emotion = analyze_emotion(sentence)
    compound_magnitude = abs(emotion["polarity"]["compound"])

    score = (
        0.45 * cues["lexical_subjectivity_ratio"]
        + 0.25 * cues["subjective_density"]
        + 0.30 * compound_magnitude
    )
    score = max(0.0, min(1.0, score))

    result = {
        "sentence": sentence,
        "subjectivity_score": round(score, 3),
        "subjectivity_label": _subjectivity_label(score),
        "cues": cues,
        "sentiment": emotion,
    }

    if use_ml_classifier:
        ml_result = classify_subjectivity_ml(sentence)
        if ml_result is not None:
            result["ml_subjectivity"] = ml_result

    return result


def analyze_text_subjectivity(text, use_ml_classifier=False, include_sentences=True):
    """
    Analyze a full text for objectivity/subjectivity and emotional tone.
    :param text: Input text (one or more sentences).
    :param use_ml_classifier: If True, also run the NLTK subjectivity-corpus classifier per sentence.
    :param include_sentences: If True, include the per-sentence breakdown in the result.
    :return: dict with an overall summary and (optionally) per-sentence detail.
    """
    if not text or not text.strip():
        return {"message": "No text provided"}

    sentences = split_into_sentences(text) or [text]
    sentence_results = [analyze_sentence(s, use_ml_classifier=use_ml_classifier) for s in sentences]

    avg_score = sum(r["subjectivity_score"] for r in sentence_results) / len(sentence_results)
    subjective_count = sum(1 for r in sentence_results if r["subjectivity_label"] == "subjective")
    objective_count = sum(1 for r in sentence_results if r["subjectivity_label"] == "objective")
    mixed_count = len(sentence_results) - subjective_count - objective_count

    overall_emotion = analyze_emotion(text)
    emotional_sentence_count = sum(1 for r in sentence_results if r["sentiment"]["is_emotional"])

    summary = {
        "overall_subjectivity_score": round(avg_score, 3),
        "overall_subjectivity_label": _subjectivity_label(avg_score),
        "subjective_sentence_ratio": round(subjective_count / len(sentence_results), 3),
        "sentence_counts": {
            "total": len(sentence_results),
            "subjective": subjective_count,
            "objective": objective_count,
            "mixed": mixed_count,
            "emotional": emotional_sentence_count,
        },
        "overall_sentiment": overall_emotion,
    }

    response = {"summary": summary}
    if include_sentences:
        response["sentences"] = sentence_results
    return response
