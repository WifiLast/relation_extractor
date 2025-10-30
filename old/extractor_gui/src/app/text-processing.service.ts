import { Injectable } from '@angular/core';
import * as lemmatizer from 'wink-lemmatizer';

@Injectable({
  providedIn: 'root'
})
export class TextProcessingService {
  constructor() {}

  /**
   * Lemmatizes a text by reducing words to their base form
   * @param text The text to lemmatize
   * @returns The lemmatized text
   */
  lemmatizeText(text: string): string {
    if (!text) return '';
    
    // Split the text into words
    const words = text.toLowerCase().split(/\s+/);
    
    // Lemmatize each word
    const lemmatizedWords = words.map(word => {
      // Remove punctuation for lemmatization
      const cleanWord = word.replace(/[^\w\s]/g, '');
      
      // Skip empty words or non-word characters
      if (!cleanWord) return word;
      
      // Try lemmatizing as different parts of speech
      // Try noun first
      let lemma = lemmatizer.noun(cleanWord);
      
      // If no change, try as verb
      if (lemma === cleanWord) {
        lemma = lemmatizer.verb(cleanWord);
      }
      
      // If still no change, try as adjective
      if (lemma === cleanWord) {
        lemma = lemmatizer.adjective(cleanWord);
      }
      
      // Return the lemma if found, otherwise the original word
      return lemma || word;
    });
    
    // Join the lemmatized words back into a sentence
    return lemmatizedWords.join(' ');
  }

  /**
   * Processes natural language text for better logic conversion
   * Combines lemmatization with other NLP techniques
   * @param text The text to process
   * @returns Processed text
   */
  processNaturalLanguage(text: string): string {
    if (!text) return '';
    
    // Step 1: Convert to lowercase and trim
    let processedText = text.toLowerCase().trim();
    
    // Step 2: Lemmatize the text
    processedText = this.lemmatizeText(processedText);
    
    // Step 3: Normalize logical connectives
    processedText = this.normalizeLogicalConnectives(processedText);
    
    // Step 4: Standardize common patterns for logical statements
    processedText = this.standardizeLogicalPatterns(processedText);
    
    return processedText;
  }
  
  /**
   * Normalizes logical connectives to standard forms
   * @param text The text to normalize
   * @returns Normalized text
   */
  normalizeLogicalConnectives(text: string): string {
    // Replace common variants of logical connectives with standard forms
    return text
      // Implication
      .replace(/if\s+(.+?)\s+then\s+(.+)/gi, '$1 implies $2')
      .replace(/(.+?)\s+only\s+if\s+(.+)/gi, '$1 implies $2')
      
      // Conjunction (AND)
      .replace(/\s+and\s+/gi, ' and ')
      .replace(/\s*,\s*and\s+/gi, ' and ')
      .replace(/\s+&\s+/g, ' and ')
      
      // Disjunction (OR)
      .replace(/\s+or\s+/gi, ' or ')
      .replace(/\s+\|\s+/g, ' or ')
      
      // Negation
      .replace(/\s+not\s+/gi, ' not ')
      .replace(/\s+isn't\s+/gi, ' is not ')
      .replace(/\s+aren't\s+/gi, ' are not ')
      .replace(/\s+don't\s+/gi, ' do not ')
      .replace(/\s+doesn't\s+/gi, ' does not ')
      
      // Universal quantification
      .replace(/\s+all\s+/gi, ' all ')
      .replace(/\s+every\s+/gi, ' all ')
      .replace(/\s+each\s+/gi, ' all ')
      
      // Existential quantification
      .replace(/\s+some\s+/gi, ' some ')
      .replace(/\s+exists\s+/gi, ' some ')
      .replace(/there\s+is\s+/gi, ' some ');
  }
  
  /**
   * Standardizes common patterns for logical statements to improve conversion
   * @param text The text to standardize
   * @returns Standardized text
   */
  standardizeLogicalPatterns(text: string): string {
    // Handle common logical statement patterns
    
    // Syllogism pattern: "All A are B. X is A. Therefore X is B."
    if (/all .+ are .+/i.test(text) && /is a/i.test(text)) {
      // Already in a good format, just ensure standardization
      return text;
    }
    
    // Property assignment pattern: "X has property Y"
    text = text.replace(/(\w+)\s+has\s+(\w+)/gi, '$1 is $2');
    
    // Relationship pattern: "X is related to Y"
    text = text.replace(/(\w+)\s+is\s+related\s+to\s+(\w+)/gi, 'related($1, $2)');
    
    // Comparison pattern: "X is greater than Y"
    text = text.replace(/(\w+)\s+is\s+greater\s+than\s+(\w+)/gi, 'greaterthan($1, $2)');
    text = text.replace(/(\w+)\s+is\s+less\s+than\s+(\w+)/gi, 'lessthan($1, $2)');
    text = text.replace(/(\w+)\s+is\s+equal\s+to\s+(\w+)/gi, 'equal($1, $2)');
    
    // Set theory patterns
    text = text.replace(/(\w+)\s+is\s+in\s+(\w+)/gi, 'in($1, $2)');
    text = text.replace(/(\w+)\s+is\s+a\s+subset\s+of\s+(\w+)/gi, 'subset($1, $2)');
    
    return text;
  }
} 