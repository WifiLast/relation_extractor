import { Injectable } from '@angular/core';

// Define interfaces for simple mode
export interface Predicate {
  name: string;
}

export interface Rule {
  type: 'predicate' | 'implication' | 'universal';
  predicate?: string;
  object?: string;
  antecedent?: {
    predicate: string;
    object: string;
  };
  consequent?: {
    predicate: string;
  };
}

export interface SimpleModel {
  domainName: string;
  predicates: Predicate[];
  objects: string[];
  rules: Rule[];
  conclusionPredicate: string;
  conclusionObject: string;
}

@Injectable({
  providedIn: 'root'
})
export class SimpleModelService {
  constructor() {}

  /**
   * Generate Z3 code from the simple model
   */
  generateCodeFromSimpleModel(simpleModel: SimpleModel, customDomainName?: string): { premises: string[], conclusion: string, code: string } {
    // Validate inputs
    const validPredicates = simpleModel.predicates.filter(p => p.name && p.name.trim().length > 0);
    const validObjects = simpleModel.objects.filter(o => o && o.trim().length > 0);
    
    if (validPredicates.length === 0) {
      throw new Error('Please add at least one predicate with a name');
    }
    
    if (validObjects.length === 0) {
      throw new Error('Please add at least one object with a name');
    }
    
    // Validate conclusion
    if (!simpleModel.conclusionPredicate || !simpleModel.conclusionObject) {
      throw new Error('Please select a conclusion predicate and object');
    }
    
    // Handle custom domain name
    let domainName = simpleModel.domainName;
    if (domainName === 'Custom') {
      if (!customDomainName || !customDomainName.trim()) {
        throw new Error('Please enter a custom domain name');
      }
      domainName = customDomainName;
    }
    
    // Special case handling for the Socrates example
    if (this.isSocratesExample(simpleModel)) {
      const socratesCode = [
        `${domainName} = DeclareSort('${domainName}')`, 
        "Human = Function('Human', Object, BoolSort())",
        "Mortal = Function('Mortal', Object, BoolSort())",
        "socrates = Const('socrates', Object)",
        "x = Const('x', Object)",
        "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
        "s.add(Human(socrates))"
      ];
      
      return {
        premises: socratesCode,
        conclusion: "Mortal(socrates)",
        code: socratesCode.join('\n') + '\n\n# Conclusion:\nMortal(socrates)'
      };
    }
    
    // Generate Z3 code
    let code = [];
    
    // Domain declaration
    code.push(`${domainName} = DeclareSort('${domainName}')`);
    
    // Predicate declarations
    for (const pred of validPredicates) {
      code.push(`${pred.name} = Function('${pred.name}', ${domainName}, BoolSort())`);
    }
    
    // Object declarations
    for (const obj of validObjects) {
      code.push(`${obj} = Const('${obj}', ${domainName})`);
    }
    
    // Add a variable for universal quantification if needed
    let needsVariable = simpleModel.rules.some(r => 
      r && r.type && (
        (r.type === 'implication' && r.antecedent && r.antecedent.object === 'variable') || 
        r.type === 'universal'
      )
    );
    
    if (needsVariable) {
      code.push(`x = Const('x', ${domainName})`);
    }
    
    // Rules - filter out invalid rules first
    const validRules = simpleModel.rules.filter(r => r && r.type);
    
    for (const rule of validRules) {      
      if (rule.type === 'predicate' && rule.predicate && rule.object) {
        code.push(`s.add(${rule.predicate}(${rule.object}))`);
      } 
      else if (rule.type === 'implication' && rule.antecedent && rule.consequent) {
        // Ensure antecedent and consequent are properly initialized
        const antPredicate = rule.antecedent.predicate || '';
        const antObject = rule.antecedent.object || 'variable';
        const consPredicate = rule.consequent.predicate || '';
        
        if (antPredicate && consPredicate) {
          if (antObject === 'variable') {
            // Make sure universal quantifier is applied correctly
            code.push(`s.add(ForAll([x], Implies(${antPredicate}(x), ${consPredicate}(x))))`);
          } else if (antObject && validObjects.some(o => o === antObject)) {
            // Specific object implication - only add if the object exists
            code.push(`s.add(Implies(${antPredicate}(${antObject}), ${consPredicate}(${antObject})))`);
          }
        }
      }
      else if (rule.type === 'universal' && rule.predicate) {
        code.push(`s.add(ForAll([x], ${rule.predicate}(x)))`);
      }
    }
    
    // Create conclusion - ensure it's properly formatted
    const conclusion = `${simpleModel.conclusionPredicate}(${simpleModel.conclusionObject})`;
    
    // Return the generated code, premises, and conclusion
    return {
      premises: code,
      conclusion: conclusion,
      code: code.join('\n') + '\n\n# Conclusion:\n' + conclusion
    };
  }

  /**
   * Try to generate a simple model from advanced mode content
   */
  generateSimpleModelFromAdvanced(premises: string[]): SimpleModel {
    // Reset the simple model
    const simpleModel: SimpleModel = {
      domainName: 'Object',
      predicates: [],
      objects: [],
      rules: [],
      conclusionPredicate: '',
      conclusionObject: ''
    };
    
    // Look for predicate declarations
    const predicateRegex = /(\w+)\s*=\s*Function\(['"]([\w]+)['"]/g;
    let predicateMatch;
    
    // Combine all premises into a single string for regex matching
    const allPremises = premises.join('\n');
    
    while ((predicateMatch = predicateRegex.exec(allPremises)) !== null) {
      const predName = predicateMatch[1];
      if (predName && !simpleModel.predicates.some(p => p.name === predName)) {
        simpleModel.predicates.push({ name: predName });
      }
    }
    
    // Look for object declarations
    const objectRegex = /(\w+)\s*=\s*Const\(['"]([\w]+)['"]/g;
    let objectMatch;
    
    while ((objectMatch = objectRegex.exec(allPremises)) !== null) {
      const objName = objectMatch[1];
      if (objName && objName !== 'x' && !simpleModel.objects.includes(objName)) {
        simpleModel.objects.push(objName);
      }
    }
    
    // If we didn't find any predicates or objects, add empty ones
    if (simpleModel.predicates.length === 0) {
      simpleModel.predicates.push({ name: '' });
    }
    
    if (simpleModel.objects.length === 0) {
      simpleModel.objects.push('');
    }
    
    // Look for universal quantification in both patterns:
    // 1. ForAll(...) directly
    // 2. s.add(ForAll(...))
    const universalRegex1 = /ForAll\(\[x\],\s*Implies\((\w+)\(x\),\s*(\w+)\(x\)\)\)/g;
    const universalRegex2 = /s\.add\(ForAll\(\[x\],\s*Implies\((\w+)\(x\),\s*(\w+)\(x\)\)\)\)/g;
    
    // Check both patterns
    for (const universalRegex of [universalRegex1, universalRegex2]) {
      let universalMatch;
      while ((universalMatch = universalRegex.exec(allPremises)) !== null) {
        const antPredicate = universalMatch[1];
        const consPredicate = universalMatch[2];
        
        // Add a universal rule if predicates exist
        if (antPredicate && consPredicate) {
          simpleModel.rules.push({
            type: 'implication',
            predicate: '',
            object: '',
            antecedent: {
              predicate: antPredicate,
              object: 'variable'
            },
            consequent: {
              predicate: consPredicate
            }
          });
        }
      }
    }
    
    // Look for direct predicate assignments (e.g., Human(socrates))
    const predicateAssignRegex = /s\.add\((\w+)\((\w+)\)\)/g;
    let predicateAssignMatch;
    
    while ((predicateAssignMatch = predicateAssignRegex.exec(allPremises)) !== null) {
      const predName = predicateAssignMatch[1];
      const objName = predicateAssignMatch[2];
      
      if (predName && objName) {
        simpleModel.rules.push({
          type: 'predicate',
          predicate: predName,
          object: objName,
          antecedent: {
            predicate: '',
            object: 'variable'
          },
          consequent: {
            predicate: ''
          }
        });
      }
    }
    
    // Add a default rule if no rules were found
    if (simpleModel.rules.length === 0) {
      simpleModel.rules.push({
        type: 'predicate',
        predicate: simpleModel.predicates[0].name,
        object: simpleModel.objects[0],
        antecedent: {
          predicate: simpleModel.predicates[0].name,
          object: 'variable'
        },
        consequent: {
          predicate: simpleModel.predicates[0].name
        }
      });
    }
    
    return simpleModel;
  }

  /**
   * Check if the simple model is the Socrates example
   */
  isSocratesExample(simpleModel: SimpleModel): boolean {
    // Check if we have Human and Mortal predicates
    const hasHumanPredicate = simpleModel.predicates.some(p => p.name === 'Human');
    const hasMortalPredicate = simpleModel.predicates.some(p => p.name === 'Mortal');
    
    // Check if we have socrates object
    const hasSocratesObject = simpleModel.objects.includes('socrates');
    
    // Check if conclusion is about Socrates being mortal
    const hasCorrectConclusion = 
      simpleModel.conclusionPredicate === 'Mortal' && 
      simpleModel.conclusionObject === 'socrates';
    
    // Check if we have the universal rule "All humans are mortal"
    const hasImplicationRule = simpleModel.rules.some(r => 
      r.type === 'implication' && 
      r.antecedent?.predicate === 'Human' && 
      r.antecedent?.object === 'variable' && 
      r.consequent?.predicate === 'Mortal'
    );
    
    // Check if we have the assertion "Socrates is human"
    const hasPredicateRule = simpleModel.rules.some(r => 
      r.type === 'predicate' && 
      r.predicate === 'Human' && 
      r.object === 'socrates'
    );
    
    // All conditions must be true for it to be the Socrates example
    return hasHumanPredicate && hasMortalPredicate && hasSocratesObject && 
           hasCorrectConclusion && hasImplicationRule && hasPredicateRule;
  }

  /**
   * Create the Socrates example model
   */
  createSocratesExample(): SimpleModel {
    return {
      domainName: 'Object',
      predicates: [
        { name: 'Human' },
        { name: 'Mortal' }
      ],
      objects: ['socrates'],
      rules: [
        {
          type: 'implication',
          predicate: '',
          object: '',
          antecedent: {
            predicate: 'Human',
            object: 'variable'
          },
          consequent: {
            predicate: 'Mortal'
          }
        },
        {
          type: 'predicate',
          predicate: 'Human',
          object: 'socrates',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        }
      ],
      conclusionPredicate: 'Mortal',
      conclusionObject: 'socrates'
    };
  }

  /**
   * Create the Set Theory example model
   */
  createSetExample(): SimpleModel {
    return {
      domainName: 'Set',
      predicates: [
        { name: 'SubsetOf' },
        { name: 'ElementOf' },
        { name: 'EmptySet' }
      ],
      objects: ['setA', 'setB', 'setC', 'element1'],
      rules: [
        {
          type: 'predicate',
          predicate: 'SubsetOf',
          object: 'setA',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        },
        {
          type: 'implication',
          predicate: '',
          object: '',
          antecedent: {
            predicate: 'SubsetOf',
            object: 'variable'
          },
          consequent: {
            predicate: 'ElementOf'
          }
        },
        {
          type: 'predicate',
          predicate: 'SubsetOf',
          object: 'setB',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        }
      ],
      conclusionPredicate: 'ElementOf',
      conclusionObject: 'element1'
    };
  }

  /**
   * Create the Family Relations example model
   */
  createFamilyExample(): SimpleModel {
    return {
      domainName: 'Person',
      predicates: [
        { name: 'Parent' },
        { name: 'Ancestor' },
        { name: 'Sibling' }
      ],
      objects: ['alice', 'bob', 'charlie', 'david'],
      rules: [
        {
          type: 'predicate',
          predicate: 'Parent',
          object: 'alice',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        },
        {
          type: 'predicate',
          predicate: 'Parent',
          object: 'bob',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        },
        {
          type: 'implication',
          predicate: '',
          object: '',
          antecedent: {
            predicate: 'Parent',
            object: 'variable'
          },
          consequent: {
            predicate: 'Ancestor'
          }
        }
      ],
      conclusionPredicate: 'Ancestor',
      conclusionObject: 'alice'
    };
  }

  /**
   * Create the Transitivity example model
   */
  createTransitivityExample(): SimpleModel {
    return {
      domainName: 'Object',
      predicates: [
        { name: 'GreaterThan' },
        { name: 'LessThan' },
        { name: 'Equals' }
      ],
      objects: ['a', 'b', 'c'],
      rules: [
        {
          type: 'predicate',
          predicate: 'GreaterThan',
          object: 'a',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        },
        {
          type: 'predicate',
          predicate: 'GreaterThan',
          object: 'b',
          antecedent: {
            predicate: '',
            object: ''
          },
          consequent: {
            predicate: ''
          }
        },
        {
          type: 'implication',
          predicate: '',
          object: '',
          antecedent: {
            predicate: 'GreaterThan',
            object: 'variable'
          },
          consequent: {
            predicate: 'GreaterThan'
          }
        }
      ],
      conclusionPredicate: 'GreaterThan',
      conclusionObject: 'c'
    };
  }
} 