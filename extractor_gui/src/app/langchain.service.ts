import { Injectable } from '@angular/core';
import { TextProcessingService } from './text-processing.service';

@Injectable({
  providedIn: 'root'
})
export class LangChainService {
  constructor(private textProcessingService: TextProcessingService) {}

  /**
   * Analyzes a sentence to extract logical structure
   * @param sentence The sentence to analyze
   * @returns Object with extracted logical structure
   */
  analyzeSentence(sentence: string): { 
    type: 'universal' | 'existential' | 'implication' | 'predicate' | 'relation' | 'unknown',
    subject?: string,
    predicate?: string,
    object?: string,
    relation?: string
  } {
    // First apply basic text processing
    const processedText = this.textProcessingService.processNaturalLanguage(sentence);
    
    // Analyze for universal quantification (All X are Y)
    if (/\ball\s+(\w+)\s+are\s+(\w+)/i.test(processedText)) {
      const match = processedText.match(/\ball\s+(\w+)\s+are\s+(\w+)/i);
      if (match) {
        return {
          type: 'universal',
          subject: match[1],
          predicate: match[2]
        };
      }
    }
    
    // Analyze for existential quantification (Some X are Y)
    if (/\bsome\s+(\w+)\s+are\s+(\w+)/i.test(processedText)) {
      const match = processedText.match(/\bsome\s+(\w+)\s+are\s+(\w+)/i);
      if (match) {
        return {
          type: 'existential',
          subject: match[1],
          predicate: match[2]
        };
      }
    }
    
    // Analyze for implication (If X then Y)
    if (/\b(\w+)\s+implies\s+(\w+)/i.test(processedText)) {
      const match = processedText.match(/\b(\w+)\s+implies\s+(\w+)/i);
      if (match) {
        return {
          type: 'implication',
          subject: match[1],
          predicate: match[2]
        };
      }
    }
    
    // Analyze for simple predication (X is Y)
    if (/\b(\w+)\s+is\s+(\w+)/i.test(processedText)) {
      const match = processedText.match(/\b(\w+)\s+is\s+(\w+)/i);
      if (match) {
        return {
          type: 'predicate',
          subject: match[1],
          predicate: match[2]
        };
      }
    }
    
    // Analyze for relations (X relation Y)
    const relationPatterns = [
      { regex: /(\w+)\s+is\s+related\s+to\s+(\w+)/i, relation: 'related_to' },
      { regex: /(\w+)\s+is\s+greater\s+than\s+(\w+)/i, relation: 'greater_than' },
      { regex: /(\w+)\s+is\s+less\s+than\s+(\w+)/i, relation: 'less_than' },
      { regex: /(\w+)\s+is\s+equal\s+to\s+(\w+)/i, relation: 'equal_to' },
      { regex: /(\w+)\s+is\s+in\s+(\w+)/i, relation: 'in' },
      { regex: /(\w+)\s+is\s+a\s+subset\s+of\s+(\w+)/i, relation: 'subset_of' }
    ];
    
    for (const pattern of relationPatterns) {
      const match = processedText.match(pattern.regex);
      if (match) {
        return {
          type: 'relation',
          subject: match[1],
          object: match[2],
          relation: pattern.relation
        };
      }
    }
    
    // If no patterns match
    return {
      type: 'unknown'
    };
  }
  
  /**
   * Converts natural language text to a more formal logical structure
   * @param text The natural language text to convert
   * @returns Structured logical representation
   */
  convertToLogicalStructure(text: string): { 
    premises: Array<{
      type: string,
      content: any
    }>,
    conclusion: {
      type: string,
      content: any
    }
  } {
    // Split by sentence endings and conjunctions
    const sentences = text.split(/\.|\?|!|;|but|however/).filter(s => s.trim().length > 0);
    
    // Last sentence is usually the conclusion in logical arguments
    const premiseSentences = sentences.slice(0, -1);
    const conclusionSentence = sentences[sentences.length - 1];
    
    // Analyze each premise
    const premises = premiseSentences.map(sentence => {
      const analysis = this.analyzeSentence(sentence);
      return {
        type: analysis.type,
        content: analysis
      };
    });
    
    // Analyze conclusion
    const conclusionAnalysis = this.analyzeSentence(conclusionSentence || '');
    
    return {
      premises,
      conclusion: {
        type: conclusionAnalysis.type,
        content: conclusionAnalysis
      }
    };
  }
} 