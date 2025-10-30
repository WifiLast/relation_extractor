import { Injectable } from '@angular/core';
import { LangChainService } from './langchain.service';

@Injectable({
  providedIn: 'root'
})
export class LogicalStructureService {
  constructor(private langChainService: LangChainService) {}

  /**
   * Analyzes the logical structure of premises and conclusion
   */
  analyzeLogicalStructure(premises: string[], conclusion: string) {
    if (!premises.some(p => p.trim()) || !conclusion.trim()) {
      return null;
    }
    
    try {
      // Combine premises into a single text with periods
      const premisesText = premises
        .filter(p => p.trim())
        .map(p => p.endsWith('.') ? p : p + '.')
        .join(' ');
        
      // Full text combines premises with conclusion
      const fullText = premisesText + ' ' + 
        (conclusion.endsWith('.') ? conclusion : conclusion + '.');
      
      // Use LangChain service to analyze
      const logicalStructure = this.langChainService.convertToLogicalStructure(fullText);
      console.log('Logical structure analysis:', logicalStructure);
      
      return logicalStructure;
    } catch (err) {
      console.warn('Could not analyze logical structure:', err);
      return null;
    }
  }

  /**
   * Generates formal logic premises and conclusion from logical structure
   */
  generateLogicFromStructure(logicalStructure: any) {
    if (!logicalStructure) {
      throw new Error('No logical structure analysis available');
    }
    
    // Create formal logic based on the analyzed structure
    let premises: string[] = [];
    let conclusion = '';
    
    // Define the domain based on the structure
    premises.push(`Object = DeclareSort('Object')`);
    
    // Create a set to keep track of functions we've already defined
    const definedFunctions = new Set<string>();
    
    // Process premises
    logicalStructure.premises.forEach((premise: {
      type: string,
      content: {
        subject?: string,
        predicate?: string,
        object?: string,
        relation?: string
      }
    }) => {
      if (premise.type === 'universal' && premise.content.subject && premise.content.predicate) {
        // Define functions for subject and predicate if not already defined
        if (!definedFunctions.has(premise.content.subject)) {
          premises.push(`${premise.content.subject} = Function('${premise.content.subject}', Object, BoolSort())`);
          definedFunctions.add(premise.content.subject);
        }
        
        if (!definedFunctions.has(premise.content.predicate)) {
          premises.push(`${premise.content.predicate} = Function('${premise.content.predicate}', Object, BoolSort())`);
          definedFunctions.add(premise.content.predicate);
        }
        
        // Add universal quantification
        premises.push(`x = Const('x', Object)`);
        premises.push(`s.add(ForAll([x], Implies(${premise.content.subject}(x), ${premise.content.predicate}(x))))`);
      }
      else if (premise.type === 'predicate' && premise.content.subject && premise.content.predicate) {
        // Define functions if not already defined
        if (!definedFunctions.has(premise.content.predicate)) {
          premises.push(`${premise.content.predicate} = Function('${premise.content.predicate}', Object, BoolSort())`);
          definedFunctions.add(premise.content.predicate);
        }
        
        // Define the subject as a constant
        premises.push(`${premise.content.subject} = Const('${premise.content.subject}', Object)`);
        
        // Add the predicate assertion
        premises.push(`s.add(${premise.content.predicate}(${premise.content.subject}))`);
      }
      else if (premise.type === 'relation' && premise.content.subject && premise.content.object && premise.content.relation) {
        // Define the relation as a function if not already defined
        const relationName = premise.content.relation.replace(/_/g, '');
        if (!definedFunctions.has(relationName)) {
          premises.push(`${relationName} = Function('${relationName}', Object, Object, BoolSort())`);
          definedFunctions.add(relationName);
        }
        
        // Define the subject and object as constants
        premises.push(`${premise.content.subject} = Const('${premise.content.subject}', Object)`);
        premises.push(`${premise.content.object} = Const('${premise.content.object}', Object)`);
        
        // Add the relation assertion
        premises.push(`s.add(${relationName}(${premise.content.subject}, ${premise.content.object}))`);
      }
    });
    
    // Process conclusion
    if (logicalStructure.conclusion.type === 'predicate' && 
        logicalStructure.conclusion.content.subject && 
        logicalStructure.conclusion.content.predicate) {
      conclusion = `${logicalStructure.conclusion.content.predicate}(${logicalStructure.conclusion.content.subject})`;
    }
    else if (logicalStructure.conclusion.type === 'relation' && 
             logicalStructure.conclusion.content.subject && 
             logicalStructure.conclusion.content.object && 
             logicalStructure.conclusion.content.relation) {
      const relationName = logicalStructure.conclusion.content.relation.replace(/_/g, '');
      conclusion = `${relationName}(${logicalStructure.conclusion.content.subject}, ${logicalStructure.conclusion.content.object})`;
    }
    
    return {
      premises,
      conclusion
    };
  }
} 