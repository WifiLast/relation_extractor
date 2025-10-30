import { Injectable } from '@angular/core';
import { Z3SolverService, ConvertedLogic } from './z3-solver.service';
import { TextProcessingService } from './text-processing.service';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class NaturalLanguageService {
  constructor(
    private z3Service: Z3SolverService,
    private textProcessingService: TextProcessingService
  ) {}

  /**
   * Convert natural language premises and conclusion to formal logic
   */
  convertToLogic(
    premises: string[], 
    conclusion: string, 
    useLemmatization: boolean
  ): Observable<ConvertedLogic> {
    // Filter out empty premises
    const validPremises = premises.filter(p => p && p.trim().length > 0);
    
    if (validPremises.length === 0) {
      throw new Error('Please enter at least one premise');
    }
    
    if (!conclusion || !conclusion.trim()) {
      throw new Error('Please enter a conclusion');
    }
    
    // Process premises and conclusion with enhanced NLP if enabled
    let processedPremises: string[];
    let processedConclusion: string;
    
    if (useLemmatization) {
      processedPremises = validPremises.map(premise => 
        this.textProcessingService.processNaturalLanguage(premise));
      processedConclusion = this.textProcessingService.processNaturalLanguage(conclusion);
      console.log('Original premises:', validPremises);
      console.log('Processed premises:', processedPremises);
      console.log('Original conclusion:', conclusion);
      console.log('Processed conclusion:', processedConclusion);
    } else {
      processedPremises = validPremises.map(premise => premise.toLowerCase().trim());
      processedConclusion = conclusion.toLowerCase().trim();
      console.log('Using unprocessed premises and conclusion (lemmatization disabled)');
    }
    
    return this.z3Service.convertNaturalLanguage(
      processedPremises, 
      processedConclusion, 
      useLemmatization
    );
  }

  /**
   * Get Socrates example in natural language
   */
  getSocratesExample(): { premises: string[], conclusion: string } {
    return {
      premises: [
        'Socrates is a human.',
        'All humans are mortal.'
      ],
      conclusion: 'Socrates is mortal.'
    };
  }
  
  /**
   * Get Set Theory example in natural language
   */
  getSetExample(): { premises: string[], conclusion: string } {
    return {
      premises: [
        'Set A is a subset of set B.',
        'Element x is in set A.'
      ],
      conclusion: 'Element x is in set B.'
    };
  }
  
  /**
   * Get Transitivity example in natural language
   */
  getTransitivityExample(): { premises: string[], conclusion: string } {
    return {
      premises: [
        'A is greater than B.',
        'B is greater than C.',
        'If x is greater than y and y is greater than z, then x is greater than z.'
      ],
      conclusion: 'A is greater than C.'
    };
  }
} 