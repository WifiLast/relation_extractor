from spacy_relation_extract import extract_relations_nltk, extract_relations

def test_direct_extraction():
    # Test sentences
    test_sentences = [
        "Socrates is a human and humans are mortal.",
        "The cat chases the mouse.",
        "Einstein developed the theory of relativity.",
        "The Earth orbits around the Sun, and the Moon orbits around the Earth."
    ]
    
    for sentence in test_sentences:
        print(f"\nTesting: '{sentence}'")
        
        # Test NLTK extraction
        nltk_relations = extract_relations_nltk(sentence)
        print(f"NLTK found {len(nltk_relations)} relations:")
        for subj, rel, obj in nltk_relations:
            print(f"  {subj} --[{rel}]--> {obj}")
        
        # Test combined extraction
        combined_relations = extract_relations(sentence)
        print(f"\nCombined method found {len(combined_relations)} relations:")
        for subj, rel, obj in combined_relations:
            print(f"  {subj} --[{rel}]--> {obj}")

if __name__ == "__main__":
    test_direct_extraction() 