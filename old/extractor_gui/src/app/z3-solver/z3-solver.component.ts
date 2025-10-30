import { Component, OnInit, AfterViewInit, Renderer2, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Z3SolverService, ConvertedLogic } from '../z3-solver.service';
import { TextProcessingService } from '../text-processing.service';
import { LangChainService } from '../langchain.service';
import { LogicalStructureService } from '../logical-structure.service';
import { SimpleModelService } from '../simple-model.service';
import { NaturalLanguageService } from '../natural-language.service';
import { CalculusService } from '../calculus.service';
import { MathBoxService } from '../mathbox.service';
import { DOCUMENT } from '@angular/common';
import * as math from 'mathjs';
import { HttpClient } from '@angular/common/http';

// Interfaces for simple mode - keep local definitions to avoid conflicts
interface Predicate {
  name: string;
}

interface Rule {
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

interface SimpleModel {
  domainName: string;
  predicates: Predicate[];
  objects: string[];
  rules: Rule[];
  conclusionPredicate: string;
  conclusionObject: string;
}

// Declare global variables from external libraries
declare var MathBox: any;
declare var THREE: any;
declare var Sigma: any;
declare var graphology: any;
declare var layoutForce: any;
declare var layoutCircular: any;
declare var layoutTree: any;
declare var layoutGrid: any;

@Component({
  selector: 'app-z3-solver',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './z3-solver.component.html',
  styleUrls: ['./z3-solver.component.css']
})
export class Z3SolverComponent implements OnInit, AfterViewInit {
  // Solver variables
  equation = '';
  constraint = '';
  result = '';
  loading = false;
  error = '';
  history: { type: string, input: string, output: string, renderedInput?: string }[] = [];
  
  // Theorem prover variables
  activeTab = 'solver'; // Default to solver tab
  premiseMode = 'simple'; // Default to simple mode for non-programmers
  premises: string[] = [''];
  conclusion = '';
  
  // Simple mode variables
  simpleModel: SimpleModel = {
    domainName: 'Object',
    predicates: [{ name: '' }],
    objects: [''],
    rules: [{
      type: 'predicate',
      predicate: '',
      object: '',
      // Initialize these to avoid undefined errors
      antecedent: {
        predicate: '',
        object: 'variable'
      },
      consequent: {
        predicate: ''
      }
    }],
    conclusionPredicate: '',
    conclusionObject: ''
  };
  
  customDomainName = '';
  generatedCode = '';
  showGeneratedCode = false;
  
  // Natural language variables
  naturalPremises: string[] = [''];
  naturalConclusion = '';
  convertedLogic: ConvertedLogic | null = null;

  // Keep a reference to the currently active input field
  currentActiveInput: HTMLInputElement | HTMLTextAreaElement | null = null;

  // Add this property for the lemmatization toggle
  useLemmatization = true;

  // Add a property to store logical structure analysis
  logicalStructure: any = null;

  // Calculus tab variables
  calcExpression = '';
  calcVariable = 'x';
  calcResult = '';
  calcLatex = '';
  nerdamerLoaded = false;

  // 3D Visualization tab variables
  mathboxLoaded = false;
  visualExpression = 'sin(x) * cos(y)';
  visualRange = [-5, 5, -5, 5];
  cleanupVisualization: (() => void) | null = null;
  visualizationActive = false;
  
  // Relation Graph tab variables
  sigmaLoaded = false;
  relationExpression = 'A→B→C';
  graphLayout = 'force';
  nodeSize = 10;
  sizeByConnections = false;
  relationActive = false;
  cleanupRelationGraph: (() => void) | null = null;

  // Relation extraction variables
  relationExtractionText = '';
  extractedRelations: Array<{subject: string, relation: string, object: string, useAsPremise?: boolean}> = [];
  extractionMethod = '';
  selectedConclusionIndex: number | null = null;
  
  // Neo4j related variables
  neo4jSearchQuery = '';
  relatedRelations: Array<{subject: string, relation: string, object: string}> = [];
  neo4jApiUrl = 'http://localhost:5000'; // Updated to match backend routes
  mongodbApiUrl = 'http://localhost:5000'; // MongoDB API URL

  constructor(
    private z3Service: Z3SolverService,
    private textProcessingService: TextProcessingService,
    private langChainService: LangChainService,
    private logicalStructureService: LogicalStructureService,
    private simpleModelService: SimpleModelService,
    private naturalLanguageService: NaturalLanguageService,
    private calculusService: CalculusService,
    private mathboxService: MathBoxService,
    private renderer: Renderer2,
    private http: HttpClient,
    @Inject(DOCUMENT) private document: Document
  ) {}

  ngOnInit() {
    // Initialize history array
    this.history = [];
    
    // Ensure premises arrays are properly initialized
    if (!this.premises || !this.premises.length) {
      this.premises = [''];
    }
    
    if (!this.naturalPremises || !this.naturalPremises.length) {
      this.naturalPremises = [''];
    }
    
    console.log("Component initialized. Natural premises:", this.naturalPremises);

    // Load Nerdamer scripts
    this.loadNerdamerScripts();

    // Load MathBox scripts
    this.loadMathBoxScripts();

    // Load Sigma.js scripts for relation graphs
    this.loadSigmaScripts();
  }

  ngAfterViewInit() {
    // Check if we need to load any scripts
    if (!this.nerdamerLoaded) {
      this.loadNerdamerScripts();
    }
    
    if (!this.mathboxLoaded) {
      this.loadMathBoxScripts();
    }
    
    // If we're starting in the visual tab, initialize the visualization
    if (this.activeTab === 'visual') {
      // Delay to ensure DOM is ready
      setTimeout(() => {
        this.directMathBoxVisualization();
      }, 500);
    }
  }

  // Replace lemmatizeText with a call to the service
  lemmatizeText(text: string): string {
    return this.textProcessingService.lemmatizeText(text);
  }

  formatExpression(expression: string): string {
    // Format for MathJax rendering
    if (!expression) return '';
    
    // Replace standard operators with LaTeX notation
    return expression
      .replace(/\*/g, '\\cdot ')
      .replace(/\//g, '\\div ')
      .replace(/\^/g, '^{')
      .replace(/([a-zA-Z0-9])\^{/g, '$1^{')
      .replace(/>/g, ' > ')
      .replace(/</g, ' < ')
      .replace(/==/g, ' = ')
      .replace(/!=/g, ' \\neq ')
      .replace(/>=/g, ' \\geq ')
      .replace(/<=/g, ' \\leq ');
  }

  simplifyExpression(expression: string): string {
    if (!expression || !expression.trim()) {
      return expression;
    }
    
    try {
      const simplified = math.simplify(expression).toString();
      return simplified;
    } catch (err) {
      // If simplification fails, return the original expression
      return expression;
    }
  }

  solveEquation() {
    if (!this.equation.trim()) {
      this.error = 'Please enter an equation';
      return;
    }
    
    this.loading = true;
    this.error = '';
    
    const simplifiedEquation = this.simplifyExpression(this.equation);
    const formattedEquation = this.formatExpression(this.equation);
    const formattedSimplifiedEquation = this.formatExpression(simplifiedEquation);
    
    this.z3Service.solveEquation(simplifiedEquation).subscribe({
      next: (response) => {
        this.result = response.message;
        this.history.push({
          type: 'Solve',
          input: this.equation + (simplifiedEquation !== this.equation ? ' → ' + simplifiedEquation : ''),
          renderedInput: `$${formattedEquation}$` + (simplifiedEquation !== this.equation ? ` → $${formattedSimplifiedEquation}$` : ''),
          output: this.result
        });
        this.loading = false;
        
        // Delay MathJax rendering and only target specific elements
        setTimeout(() => {
          // Find the newly added history item
          const historyItems = document.querySelectorAll('.history-input.math-render');
          if (historyItems.length > 0) {
            // Only process the math-render elements
            //this.renderMathOnlyInDesignatedElements();
          }
        }, 100);
      },
      error: (err) => {
        this.error = 'Error solving equation: ' + (err.error?.message || err.message || 'Unknown error');
        this.loading = false;
      }
    });
  }

  addConstraint() {
    if (!this.constraint.trim()) {
      this.error = 'Please enter a constraint';
      return;
    }
    
    this.loading = true;
    this.error = '';
    
    const simplifiedConstraint = this.simplifyExpression(this.constraint);
    const formattedConstraint = this.formatExpression(this.constraint);
    const formattedSimplifiedConstraint = this.formatExpression(simplifiedConstraint);
    
    this.z3Service.addConstraint(simplifiedConstraint).subscribe({
      next: (response) => {
        this.result = 'Constraint added: ' + response.constraint;
        this.history.push({
          type: 'Constraint',
          input: this.constraint + (simplifiedConstraint !== this.constraint ? ' → ' + simplifiedConstraint : ''),
          renderedInput: `$${formattedConstraint}$` + (simplifiedConstraint !== this.constraint ? ` → $${formattedSimplifiedConstraint}$` : ''),
          output: this.result
        });
        this.loading = false;
        
        // Delay MathJax rendering and only target specific elements
        setTimeout(() => {
          // Find the newly added history item
          const historyItems = document.querySelectorAll('.history-input.math-render');
          if (historyItems.length > 0) {
            // Only process the math-render elements
            //this.renderMathOnlyInDesignatedElements();
          }
        }, 100);
      },
      error: (err) => {
        this.error = 'Error adding constraint: ' + (err.error?.message || err.message || 'Unknown error');
        this.loading = false;
      }
    });
  }

  checkSatisfiability() {
    this.loading = true;
    this.error = '';
    
    this.z3Service.checkSatisfiability().subscribe({
      next: (response) => {
        this.result = response.message;
        this.history.push({
          type: 'Check',
          input: 'Satisfiability check',
          output: this.result
        });
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Error checking satisfiability: ' + (err.error?.message || err.message || 'Unknown error');
        this.loading = false;
      }
    });
  }
  
  // Theorem prover methods - Advanced mode
  addPremise() {
    // Create a new array to avoid reference issues
    this.premises = [...this.premises, ''];
  }
  
  removePremise(index: number) {
    if (this.premises.length > 1 && index >= 0 && index < this.premises.length) {
      // Create a new array without the item at index
      this.premises = [
        ...this.premises.slice(0, index),
        ...this.premises.slice(index + 1)
      ];
    }
  }
  
  loadSocratesExample() {
    this.premiseMode = 'advanced';
    
    // Reset errors and results
    this.error = '';
    this.result = '';
    
    this.premises = [
      "Object = DeclareSort('Object')",
      "Human = Function('Human', Object, BoolSort())",
      "Mortal = Function('Mortal', Object, BoolSort())",
      "socrates = Const('socrates', Object)",
      "x = Const('x', Object)",
      "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
      "s.add(Human(socrates))"
    ];
    
    this.conclusion = "Mortal(socrates)";
  }
  
  proveTheorem() {
    // Filter out empty premises
    const validPremises = this.premises.filter(p => p && p.trim().length > 0);
    
    if (validPremises.length === 0) {
      this.error = 'Please enter at least one premise';
      return;
    }
    
    if (!this.conclusion || !this.conclusion.trim()) {
      this.error = 'Please enter a conclusion';
      return;
    }
    
    // Make sure the conclusion contains parentheses (basic format check)
    if (!this.conclusion.includes('(') || !this.conclusion.includes(')')) {
      this.error = 'Conclusion should be in the form Predicate(Object), e.g., Mortal(socrates)';
      return;
    }
    
    this.loading = true;
    this.error = '';
    this.result = '';
    
    this.z3Service.proveTheorem(validPremises, this.conclusion).subscribe({
      next: (response) => {
        if (response && response.message) {
          this.result = response.message;
          
          // Format the input for history display only - don't modify the actual inputs
          const premisesText = validPremises.join('\n');
          
          this.history.push({
            type: 'Theorem',
            input: `Premises:\n${premisesText}\n\nConclusion:\n${this.conclusion}`,
            output: this.result
          });
        } else {
          this.error = 'Received empty response from the server';
        }
        
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Error proving theorem: ' + (err.error?.message || err.message || 'Unknown error');
        this.loading = false;
      }
    });
  }

  // Theorem prover methods - Simple mode
  addPredicate() {
    // Create a new array to avoid reference issues
    this.simpleModel.predicates = [...this.simpleModel.predicates, { name: '' }];
  }
  
  removePredicate(index: number) {
    if (this.simpleModel.predicates.length > 1 && index >= 0 && index < this.simpleModel.predicates.length) {
      // Create a new array without the item at index
      this.simpleModel.predicates = [
        ...this.simpleModel.predicates.slice(0, index),
        ...this.simpleModel.predicates.slice(index + 1)
      ];
    }
  }
  
  addObject() {
    // Create a new array to avoid reference issues
    this.simpleModel.objects = [...this.simpleModel.objects, ''];
  }
  
  removeObject(index: number) {
    if (this.simpleModel.objects.length > 1 && index >= 0 && index < this.simpleModel.objects.length) {
      // Create a new array without the item at index
      this.simpleModel.objects = [
        ...this.simpleModel.objects.slice(0, index),
        ...this.simpleModel.objects.slice(index + 1)
      ];
    }
  }
  
  addRule() {
    // Create a new rule with proper initialization
    const newRule: Rule = {
      type: 'predicate',
      predicate: this.simpleModel.predicates.length > 0 ? this.simpleModel.predicates[0].name : '',
      object: this.simpleModel.objects.length > 0 ? this.simpleModel.objects[0] : '',
      // Initialize antecedent and consequent to avoid undefined errors
      antecedent: {
        predicate: this.simpleModel.predicates.length > 0 ? this.simpleModel.predicates[0].name : '',
        object: 'variable'
      },
      consequent: {
        predicate: this.simpleModel.predicates.length > 0 ? this.simpleModel.predicates[0].name : ''
      }
    };
    
    // Create a new array to avoid reference issues
    this.simpleModel.rules = [...this.simpleModel.rules, newRule];
  }
  
  removeRule(index: number) {
    if (this.simpleModel.rules.length > 1 && index >= 0 && index < this.simpleModel.rules.length) {
      // Create a new array without the item at index
      this.simpleModel.rules = [
        ...this.simpleModel.rules.slice(0, index),
        ...this.simpleModel.rules.slice(index + 1)
      ];
    }
  }
  
  // Special method to handle the Socrates example correctly
  loadSimpleSocratesExample() {
    // Reset any previous errors and results
    this.error = '';
    this.result = '';
    
    this.simpleModel = this.simpleModelService.createSocratesExample();
    
    // Set the conclusion
    this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
    
    // Generate the Z3 code with our own specialized code instead of using generateCode
    const socratesCode = [
      `${this.simpleModel.domainName} = DeclareSort('${this.simpleModel.domainName}')`, 
      "Human = Function('Human', Object, BoolSort())",
      "Mortal = Function('Mortal', Object, BoolSort())",
      "socrates = Const('socrates', Object)",
      "x = Const('x', Object)",
      "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
      "s.add(Human(socrates))"
    ];
    
    this.premises = [...socratesCode];
    this.generatedCode = socratesCode.join('\n') + '\n\n# Conclusion:\n' + this.conclusion;
    this.showGeneratedCode = true;
  }
  
  // Helper method to detect if we're proving the Socrates syllogism
  isSocratesExample() {
    return this.simpleModelService.isSocratesExample(this.simpleModel);
  }

  // Prove theorem from simple mode
  proveSimpleTheorem() {
    // Special case for the Socrates example
    if (this.isSocratesExample()) {
      // Reset any errors and results
      this.error = '';
      this.result = '';
      
      // Set up the specialized Socrates example code
      const socratesCode = [
        `${this.simpleModel.domainName} = DeclareSort('${this.simpleModel.domainName}')`, 
        "Human = Function('Human', Object, BoolSort())",
        "Mortal = Function('Mortal', Object, BoolSort())",
        "socrates = Const('socrates', Object)",
        "x = Const('x', Object)",
        "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
        "s.add(Human(socrates))"
      ];
      
      this.premises = [...socratesCode];
      this.conclusion = "Mortal(socrates)";
      this.generatedCode = socratesCode.join('\n') + '\n\n# Conclusion:\n' + this.conclusion;
      this.showGeneratedCode = true;
      
      // Now prove the theorem
      this.proveTheorem();
      return;
    }
    
    // For all other cases, use the normal flow
    this.generateCode();
    
    // Only proceed if there are no errors and conclusion is set
    if (!this.error && this.conclusion && this.conclusion.trim()) {
      this.proveTheorem();
    }
  }
  
  // Toggle the display of generated code
  toggleGeneratedCode() {
    // If no code has been generated yet, generate it
    if (!this.generatedCode) {
      this.generateCode();
    } else {
      // Otherwise just toggle the display
      this.showGeneratedCode = !this.showGeneratedCode;
    }
  }

  clearHistory() {
    this.history = [];
  }

  initializeRuleProperties(index: number) {
    const rule = this.simpleModel.rules[index];
    const defaultPredicate = this.simpleModel.predicates.length > 0 ? this.simpleModel.predicates[0].name : '';
    const defaultObject = this.simpleModel.objects.length > 0 ? this.simpleModel.objects[0] : '';
    
    // Make sure required properties are initialized based on rule type
    if (rule.type === 'predicate') {
      if (!rule.predicate) rule.predicate = defaultPredicate;
      if (!rule.object) rule.object = defaultObject;
    } 
    else if (rule.type === 'implication') {
      if (!rule.antecedent) {
        rule.antecedent = {
          predicate: defaultPredicate,
          object: 'variable'
        };
      }
      if (!rule.consequent) {
        rule.consequent = {
          predicate: defaultPredicate
        };
      }
    }
    else if (rule.type === 'universal') {
      if (!rule.predicate) rule.predicate = defaultPredicate;
    }
  }

  // Natural Language Tab Methods
  addNaturalPremise() {
    // Create a new array to avoid reference issues
    this.naturalPremises = [...this.naturalPremises, ''];
  }
  
  removeNaturalPremise(index: number) {
    if (this.naturalPremises.length > 1 && index >= 0 && index < this.naturalPremises.length) {
      // Create a new array without the item at index
      this.naturalPremises = [
        ...this.naturalPremises.slice(0, index),
        ...this.naturalPremises.slice(index + 1)
      ];
    }
  }
  
  loadNaturalSocratesExample() {
    const example = this.naturalLanguageService.getSocratesExample();
    
    // Create a new array to avoid reference issues
    this.naturalPremises = [...example.premises];
    this.naturalConclusion = example.conclusion;
    
    // Clear any previous errors and results
    this.error = '';
    this.result = '';
    this.convertedLogic = null;
    
    console.log("Loaded Socrates example. Natural premises:", this.naturalPremises);
  }
  
  loadNaturalSetExample() {
    const example = this.naturalLanguageService.getSetExample();
    
    // Create a new array to avoid reference issues
    this.naturalPremises = [...example.premises];
    this.naturalConclusion = example.conclusion;
    
    // Clear any previous errors and results
    this.error = '';
    this.result = '';
    this.convertedLogic = null;
    
    console.log("Loaded Set example. Natural premises:", this.naturalPremises);
  }
  
  loadNaturalTransitivityExample() {
    const example = this.naturalLanguageService.getTransitivityExample();
    
    // Create a new array to avoid reference issues
    this.naturalPremises = [...example.premises];
    this.naturalConclusion = example.conclusion;
    
    // Clear any previous errors and results
    this.error = '';
    this.result = '';
    this.convertedLogic = null;
    
    console.log("Loaded Transitivity example. Natural premises:", this.naturalPremises);
  }
  
  // Replace processNaturalLanguage with a call to the service
  processNaturalLanguage(text: string): string {
    return this.textProcessingService.processNaturalLanguage(text);
  }

  // Add method to analyze natural language input
  analyzeLogicalStructure() {
    // Only analyze if we have some input
    if (!this.naturalPremises.some(p => p.trim()) || !this.naturalConclusion.trim()) {
      this.error = 'Please enter premises and conclusion to analyze';
      return;
    }
    
    try {
      this.logicalStructure = this.logicalStructureService.analyzeLogicalStructure(
        this.naturalPremises,
        this.naturalConclusion
      );
      
      if (this.logicalStructure) {
        // Show the structure in the result area
        this.result = 'Logical structure analyzed successfully. Check console for details.';
      } else {
        this.error = 'Could not analyze logical structure';
      }
    } catch (err) {
      console.error('Error analyzing logical structure:', err);
      this.error = 'Error analyzing logical structure: ' + err;
    }
  }

  // Update convertToLogic to use the NaturalLanguageService
  convertToLogic() {
    try {
      // Always analyze the logical structure first to provide better understanding
      this.analyzeLogicalStructure();
      
      this.loading = true;
      this.error = '';
      
      this.naturalLanguageService.convertToLogic(
        this.naturalPremises, 
        this.naturalConclusion, 
        this.useLemmatization
      ).subscribe({
        next: (response) => {
          this.convertedLogic = response;
          this.loading = false;
          
          // Update the result to indicate both operations completed
          this.result = 'Natural language successfully converted to formal logic.';
          
          // Add this conversion to history
          this.history.push({
            type: 'NL-to-Logic',
            input: `Original: ${this.naturalPremises.join(' | ')} → ${this.naturalConclusion}`,
            output: `Converted to formal logic successfully.`
          });
        },
        error: (err) => {
          this.error = 'Error converting natural language: ' + (err.error?.message || err.message || 'Unknown error');
          this.loading = false;
        }
      });
    } catch (err) {
      this.error = 'Error preparing natural language conversion: ' + (err instanceof Error ? err.message : String(err));
      this.loading = false;
    }
  }
  
  // Add a method to toggle lemmatization
  toggleLemmatization() {
    this.useLemmatization = !this.useLemmatization;
    console.log(`Lemmatization ${this.useLemmatization ? 'enabled' : 'disabled'}`);
    
    // Clear any existing converted logic when toggling
    // This forces the user to re-convert with the new setting
    this.convertedLogic = null;
    
    // Clear any existing logical structure analysis
    this.logicalStructure = null;
    
    // Update the result to inform the user
    this.result = `Lemmatization ${this.useLemmatization ? 'enabled' : 'disabled'}. Please convert text again with the new setting.`;
    
    // Clear any existing error
    this.error = '';
  }

  useConvertedLogic() {
    if (!this.convertedLogic) {
      this.error = "No converted logic available. Please convert natural language first.";
      return;
    }
    
    // Switch to theorem prover tab
    this.activeTab = 'theorem';
    this.premiseMode = 'advanced';
    
    // Make sure to add empty premises if needed
    if (this.premises.length === 0) {
      this.premises = [''];
    }
    
    // Transfer the converted logic - replace existing premises with the converted ones
    this.premises = [...this.convertedLogic.premises];
    
    // Set the conclusion
    this.conclusion = this.convertedLogic.conclusion;
    
    // Clear any existing errors
    this.error = '';
    
    // Display a success message
    this.result = 'Successfully transferred logic to Theorem Prover tab. You can now prove the theorem.';
  }
  
  proveConvertedLogic() {
    if (!this.convertedLogic) {
      this.error = 'No converted logic available. Please convert natural language first.';
      return;
    }
    
    if (!this.convertedLogic.premises || !this.convertedLogic.premises.length) {
      this.error = 'No premises available in the converted logic.';
      return;
    }
    
    if (!this.convertedLogic.conclusion) {
      this.error = 'No conclusion available in the converted logic.';
      return;
    }
    
    this.loading = true;
    this.error = '';
    this.result = '';
    
    // Make a copy of the premises to avoid mutation issues
    const premises = [...this.convertedLogic.premises];
    const conclusion = this.convertedLogic.conclusion;
    
    this.z3Service.proveTheorem(premises, conclusion).subscribe({
      next: (response) => {
        this.result = response.message;
        
        // Format the input for history display only
        const premisesText = premises.join('\n');
        
        // Build a more comprehensive history entry
        let historyInput = `Natural Language Premises:\n${this.naturalPremises.join('\n')}\n\nNatural Language Conclusion:\n${this.naturalConclusion}\n\n`;
        
        // Add logical structure if available
        if (this.logicalStructure) {
          historyInput += `Logical Structure Analysis: Available\n\n`;
        }
        
        historyInput += `Converted Premises:\n${premisesText}\n\nConverted Conclusion:\n${conclusion}`;
        
        this.history.push({
          type: 'Natural Language',
          input: historyInput,
          output: this.result
        });
        
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Error proving theorem: ' + (err.error?.message || err.message || 'Unknown error');
        this.loading = false;
      }
    });
  }

  // Updated functions to handle input events from the template

  updateEquation(value: string) {
    this.equation = value;
  }

  updateConstraint(value: string) {
    this.constraint = value;
  }

  updateCustomDomain(value: string) {
    this.customDomainName = value;
  }

  updatePremise(value: string, index: number) {
    if (index >= 0 && index < this.premises.length) {
      this.premises[index] = value;
    }
  }

  updateNaturalPremise(value: string, index: number) {
    if (index >= 0 && index < this.naturalPremises.length) {
      // Store the original value
      this.naturalPremises[index] = value;
      
      // Log the lemmatized version for debugging
      console.log(`Original: "${value}"`);
      console.log(`Lemmatized: "${this.lemmatizeText(value)}"`);
    }
  }

  updateNaturalConclusion(value: string) {
    // Store the original value
    this.naturalConclusion = value;
    
    // Log the lemmatized version for debugging
    console.log(`Original conclusion: "${value}"`);
    console.log(`Lemmatized conclusion: "${this.lemmatizeText(value)}"`);
  }

  // Debug method to help troubleshoot premise issues
  debugPremises() {
    console.log("Current premises array:", this.premises);
    
    // Show premises in the UI for easier debugging
    const validPremises = this.premises.filter(p => p && p.trim().length > 0);
    
    if (validPremises.length === 0) {
      this.result = "No valid premises found. Current premises array: " + JSON.stringify(this.premises);
    } else {
      this.result = "Valid premises: " + JSON.stringify(validPremises) + 
                   "\nRaw premises array: " + JSON.stringify(this.premises);
    }
  }

  // Debug method for natural language premises
  debugNaturalPremises() {
    console.log("Current natural premises array:", this.naturalPremises);
    
    // Show premises in the UI for easier debugging
    const validPremises = this.naturalPremises.filter(p => p && p.trim().length > 0);
    
    if (validPremises.length === 0) {
      this.result = "No valid natural language premises found. Current premises array: " + JSON.stringify(this.naturalPremises);
      console.log("No valid natural language premises found.");
    } else {
      this.result = "Valid natural language premises: " + JSON.stringify(validPremises) + 
                   "\nRaw natural premises array: " + JSON.stringify(this.naturalPremises);
      console.log("Valid natural language premises:", validPremises);
    }
    
    // Check if the array contains any undefined or null values
    const hasInvalidValues = this.naturalPremises.some(p => p === undefined || p === null);
    if (hasInvalidValues) {
      this.result += "\nWARNING: Array contains undefined or null values!";
      console.warn("Natural premises array contains undefined or null values!");
      
      // Fix the array by replacing invalid values with empty strings
      this.naturalPremises = this.naturalPremises.map(p => p === undefined || p === null ? '' : p);
      console.log("Fixed natural premises array:", this.naturalPremises);
    }
  }
  
  // Debug method for natural language conclusion
  debugConclusion() {
    console.log("Current natural conclusion:", this.naturalConclusion);
    
    if (!this.naturalConclusion || !this.naturalConclusion.trim()) {
      this.result = "No valid natural language conclusion found. Current conclusion: " + JSON.stringify(this.naturalConclusion);
      console.log("No valid natural language conclusion found.");
    } else {
      this.result = "Valid natural language conclusion: " + JSON.stringify(this.naturalConclusion);
      console.log("Valid natural language conclusion:", this.naturalConclusion);
    }
    
    // Ensure conclusion is initialized
    if (this.naturalConclusion === undefined || this.naturalConclusion === null) {
      this.naturalConclusion = '';
      this.result += "\nWARNING: Conclusion was undefined or null and has been initialized!";
      console.warn("Natural conclusion was undefined or null and has been initialized!");
    }
  }
  
  // Debug method for simple mode predicates
  debugPredicates() {
    console.log("Current predicates:", this.simpleModel.predicates);
    
    // Show predicates in the UI for easier debugging
    const validPredicates = this.simpleModel.predicates.filter(p => p && p.name && p.name.trim().length > 0);
    
    if (validPredicates.length === 0) {
      this.result = "No valid predicates found. Current predicates array: " + JSON.stringify(this.simpleModel.predicates);
      console.log("No valid predicates found.");
    } else {
      this.result = "Valid predicates: " + JSON.stringify(validPredicates) + 
                   "\nRaw predicates array: " + JSON.stringify(this.simpleModel.predicates);
      console.log("Valid predicates:", validPredicates);
    }
    
    // Check if the array contains any invalid values
    const hasInvalidValues = this.simpleModel.predicates.some(p => !p || !p.name);
    if (hasInvalidValues) {
      this.result += "\nWARNING: Predicates array contains invalid values!";
      console.warn("Predicates array contains invalid values!");
      
      // Fix the array by replacing invalid values
      this.simpleModel.predicates = this.simpleModel.predicates.map(p => {
        if (!p) return { name: '' };
        if (!p.name) p.name = '';
        return p;
      });
      console.log("Fixed predicates array:", this.simpleModel.predicates);
    }
  }
  
  // Debug method for simple mode objects
  debugObjects() {
    console.log("Current objects:", this.simpleModel.objects);
    
    // Show objects in the UI for easier debugging
    const validObjects = this.simpleModel.objects.filter(o => o && o.trim().length > 0);
    
    if (validObjects.length === 0) {
      this.result = "No valid objects found. Current objects array: " + JSON.stringify(this.simpleModel.objects);
      console.log("No valid objects found.");
    } else {
      this.result = "Valid objects: " + JSON.stringify(validObjects) + 
                   "\nRaw objects array: " + JSON.stringify(this.simpleModel.objects);
      console.log("Valid objects:", validObjects);
    }
    
    // Check if the array contains any invalid values
    const hasInvalidValues = this.simpleModel.objects.some(o => o === undefined || o === null);
    if (hasInvalidValues) {
      this.result += "\nWARNING: Objects array contains undefined or null values!";
      console.warn("Objects array contains undefined or null values!");
      
      // Fix the array by replacing invalid values with empty strings
      this.simpleModel.objects = this.simpleModel.objects.map(o => o === undefined || o === null ? '' : o);
      console.log("Fixed objects array:", this.simpleModel.objects);
    }
  }

  // Methods for switching between simple and advanced modes
  switchToSimpleMode() {
    console.log("Switching to simple mode");
    
    // If we have content in advanced mode, transfer it to simple mode
    if (this.premiseMode === 'advanced' && this.premises.length > 0 && this.premises[0].trim()) {
      console.log("Transferring content from advanced to simple mode");
      
      // Check if current content is the Socrates example
      const isSocratesAdvanced = 
        this.premises.some(p => p.includes('Human = Function')) && 
        this.premises.some(p => p.includes('Mortal = Function')) &&
        this.premises.some(p => p.includes('socrates = Const')) &&
        (
          this.premises.some(p => p.includes('ForAll([x], Implies(Human(x), Mortal(x)))')) ||
          this.premises.some(p => p.includes('s.add(ForAll([x], Implies(Human(x), Mortal(x))))'))
        ) &&
        this.premises.some(p => p.includes('s.add(Human(socrates))')) &&
        this.conclusion === 'Mortal(socrates)';
      
      if (isSocratesAdvanced) {
        // Load the simple Socrates example directly
        this.loadSimpleSocratesExample();
      } else {
        // Generate a simple model from the advanced mode content if possible
        this.tryGenerateSimpleModelFromAdvanced();
      }
    }
    
    this.premiseMode = 'simple';
    console.log("Now in simple mode");
  }
  
  switchToAdvancedMode() {
    console.log("Switching to advanced mode");
    
    // If we have content in simple mode, transfer it to advanced mode
    if (this.premiseMode === 'simple' && 
        this.simpleModel.predicates.length > 0 && 
        this.simpleModel.objects.length > 0 && 
        this.simpleModel.predicates[0].name.trim() && 
        this.simpleModel.objects[0].trim()) {
      
      console.log("Transferring content from simple to advanced mode");
      
      // Generate code from the simple model and use it in advanced mode
      this.generateCode();
      
      // Make sure the conclusion is set
      if (this.simpleModel.conclusionPredicate && this.simpleModel.conclusionObject) {
        this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
      }
    }
    
    this.premiseMode = 'advanced';
    console.log("Now in advanced mode");
  }
  
  // Try to generate a simple model from advanced mode content
  tryGenerateSimpleModelFromAdvanced() {
    this.simpleModel = this.simpleModelService.generateSimpleModelFromAdvanced(this.premises);
    console.log("Generated simple model from advanced mode:", this.simpleModel);
  }

  // Update the simple mode conclusion when the predicate or object changes
  updateSimpleConclusion() {
    // Only update if both predicate and object are set
    if (!this.simpleModel.conclusionPredicate || !this.simpleModel.conclusionObject) {
      return;
    }
    
    // Update the conclusion for the advanced mode
    this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
    
    // If we've already generated code, update it
    if (this.generatedCode) {
      // Update the conclusion part of the generated code
      const conclusionLine = `# Conclusion:\n${this.conclusion}`;
      
      // Split the generated code at the conclusion marker
      const codeParts = this.generatedCode.split('# Conclusion:');
      if (codeParts.length > 1) {
        this.generatedCode = codeParts[0] + conclusionLine;
      } else {
        this.generatedCode += '\n\n' + conclusionLine;
      }
    }
  }

  // Add the missing update methods

  updatePredicate(value: string, index: number) {
    if (index >= 0 && index < this.simpleModel.predicates.length) {
      this.simpleModel.predicates[index].name = value;
    }
  }

  updateObject(value: string, index: number) {
    if (index >= 0 && index < this.simpleModel.objects.length) {
      this.simpleModel.objects[index] = value;
    }
  }

  // Helper method for trackBy functionality
  trackByIndex(index: number): number {
    return index;
  }

  loadSetExample() {
    // Reset any previous errors and results
    this.error = '';
    this.result = '';
    
    this.simpleModel = this.simpleModelService.createSetExample();
    
    // Update conclusion first
    this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
    
    // Then generate the code
    this.generateCode();
  }
  
  loadFamilyExample() {
    // Reset any previous errors and results
    this.error = '';
    this.result = '';
    
    this.simpleModel = this.simpleModelService.createFamilyExample();
    
    // Update conclusion first
    this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
    
    // Then generate the code
    this.generateCode();
  }
  
  loadTransitivityExample() {
    // Reset any previous errors and results
    this.error = '';
    this.result = '';
    
    this.simpleModel = this.simpleModelService.createTransitivityExample();
    
    // Update conclusion first
    this.conclusion = `${this.simpleModel.conclusionPredicate}(${this.simpleModel.conclusionObject})`;
    
    // Then generate the code
    this.generateCode();
  }
  
  generateCode() {
    try {
      const result = this.simpleModelService.generateCodeFromSimpleModel(this.simpleModel, this.customDomainName);
      this.premises = result.premises;
      this.conclusion = result.conclusion;
      this.generatedCode = result.code;
      this.showGeneratedCode = true;
      this.error = '';
    } catch (err) {
      this.error = err instanceof Error ? err.message : String(err);
    }
  }

  // Method to use the analyzed logical structure directly
  useAnalyzedStructure() {
    if (!this.logicalStructure) {
      this.error = 'No logical structure analysis available. Please analyze first.';
      return;
    }
    
    try {
      const generatedLogic = this.logicalStructureService.generateLogicFromStructure(this.logicalStructure);
      
      // Create the convertedLogic object
      this.convertedLogic = {
        premises: generatedLogic.premises,
        conclusion: generatedLogic.conclusion
      };
      
      // Show success message
      this.result = 'Successfully generated formal logic from analyzed structure.';
      this.error = '';
      
    } catch (err) {
      console.error('Error generating logic from structure:', err);
      this.error = 'Could not generate logic from analyzed structure: ' + (err instanceof Error ? err.message : String(err));
    }
  }

  /**
   * Loads Nerdamer scripts for calculus operations
   */
  private loadNerdamerScripts() {
    const scripts = [
      'https://cdn.jsdelivr.net/npm/nerdamer@1.1.13/nerdamer.core.min.js',
      'https://cdn.jsdelivr.net/npm/nerdamer@1.1.13/Algebra.min.js',
      'https://cdn.jsdelivr.net/npm/nerdamer@1.1.13/Calculus.min.js',
      'https://cdn.jsdelivr.net/npm/nerdamer@1.1.13/Solve.min.js',
      'https://cdn.jsdelivr.net/npm/nerdamer@1.1.13/Extra.min.js'
    ];

    // Load scripts sequentially to ensure proper dependency resolution
    this.loadScriptSequentially(scripts, 0);
  }

  /**
   * Loads scripts one after another in sequence
   * @param scripts Array of script URLs to load
   * @param index Current script index to load
   */
  private loadScriptSequentially(scripts: string[], index: number) {
    if (index >= scripts.length) {
      console.log('All Nerdamer scripts loaded successfully');
      
      // Verify Nerdamer is actually loaded correctly
      this.verifyNerdamerLoaded();
      return;
    }

    const scriptElement = this.renderer.createElement('script');
    scriptElement.src = scripts[index];
    scriptElement.onload = () => {
      console.log(`Script loaded: ${scripts[index]}`);
      // Load the next script only after the current one is loaded
      this.loadScriptSequentially(scripts, index + 1);
    };
    scriptElement.onerror = () => {
      console.error(`Failed to load script: ${scripts[index]}`);
      // Try to continue loading next script even if one fails
      this.loadScriptSequentially(scripts, index + 1);
    };
    this.renderer.appendChild(this.document.body, scriptElement);
  }

  /**
   * Verifies that Nerdamer is loaded and functions are available
   */
  private verifyNerdamerLoaded() {
    // Give a short delay to ensure scripts are fully initialized
    setTimeout(() => {
      try {
        if (typeof nerdamer === 'undefined') {
          console.error('Nerdamer is not defined after loading scripts');
          this.error = 'Failed to load Nerdamer library. Please refresh the page.';
          return;
        }

        // Test basic functionality
        if (typeof nerdamer === 'function') {
          // Test each required operation
          const testExpr = nerdamer('x^2');
          
          let canIntegrate = false;
          let canDifferentiate = false;
          
          // Check integration
          try {
            if (typeof nerdamer.integrate === 'function') {
              nerdamer.integrate('x^2', 'x');
              canIntegrate = true;
            } else if (testExpr.integrate) {
              testExpr.integrate('x');
              canIntegrate = true;
            }
          } catch (e) {
            console.error('Integration test failed:', e);
          }
          
          // Check differentiation
          try {
            if (typeof nerdamer.diff === 'function') {
              nerdamer.diff('x^2', 'x');
              canDifferentiate = true;
            } else if (testExpr.diff) {
              testExpr.diff('x');
              canDifferentiate = true;
            }
          } catch (e) {
            console.error('Differentiation test failed:', e);
          }
          
          if (canIntegrate && canDifferentiate) {
            console.log('Nerdamer verified: core, integration, and differentiation all work');
            this.nerdamerLoaded = true;
            this.calculusService.setNerdamerLoaded();
          } else {
            console.error('Nerdamer partially loaded. Integration:', canIntegrate, 'Differentiation:', canDifferentiate);
            this.error = 'Nerdamer calculus functionality not fully available. Some operations may not work.';
          }
        } else {
          console.error('Nerdamer is not a function');
          this.error = 'Nerdamer library loaded incorrectly. Please refresh the page.';
        }
      } catch (e) {
        console.error('Error verifying Nerdamer:', e);
        this.error = 'Error initializing Nerdamer: ' + e;
      }
    }, 500);
  }

  /**
   * Loads MathBox scripts for 3D visualization
   */
  public loadMathBoxScripts() {
    const scripts = [
      // Use specific versions for stability
      'https://cdn.jsdelivr.net/npm/three@0.137.0/build/three.min.js',
      'https://cdn.jsdelivr.net/npm/three@0.137.0/examples/js/controls/OrbitControls.js',
      // Try a different CDN for MathBox
      'https://cdn.jsdelivr.net/npm/mathbox@latest/build/bundle/mathbox.js'
    ];

    console.log('Loading MathBox scripts...');
    
    // First check if THREE is already loaded
    if (typeof THREE !== 'undefined') {
      console.log('THREE is already loaded');
      // If THREE is loaded but not OrbitControls, load just that
      if (typeof THREE.OrbitControls === 'undefined') {
        console.log('Loading OrbitControls...');
        this.loadSingleScript('https://unpkg.com/three@0.136.0/examples/js/controls/OrbitControls.js', () => {
          // Once OrbitControls is loaded, load MathBox
          console.log('Loading MathBox from alternate source...');
          this.loadSingleScript('https://cdn.jsdelivr.net/gh/unconed/mathbox@latest/build/mathbox-bundle.js', () => {
            this.verifyMathBoxLoaded();
          });
        });
        return;
      }
    }

    // Load scripts sequentially to ensure proper dependency resolution
    this.loadMathBoxScriptSequentially(scripts, 0);
  }
  
  /**
   * Load a single script and call a callback when done
   */
  private loadSingleScript(src: string, callback: () => void) {
    const scriptElement = this.renderer.createElement('script');
    scriptElement.src = src;
    scriptElement.onload = callback;
    scriptElement.onerror = (e: Event) => {
      console.error(`Failed to load script: ${src}`, e);
    };
    this.renderer.appendChild(this.document.body, scriptElement);
  }

  /**
   * Loads MathBox scripts one after another in sequence
   */
  private loadMathBoxScriptSequentially(scripts: string[], index: number) {
    if (index >= scripts.length) {
      console.log('All MathBox scripts loaded successfully');
      this.verifyMathBoxLoaded();
      return;
    }

    const scriptElement = this.renderer.createElement('script');
    scriptElement.src = scripts[index];
    scriptElement.onload = () => {
      console.log(`MathBox script loaded: ${scripts[index]}`);
      // Load the next script only after the current one is loaded
      this.loadMathBoxScriptSequentially(scripts, index + 1);
    };
    scriptElement.onerror = () => {
      console.error(`Failed to load MathBox script: ${scripts[index]}`);
      // Try to continue loading next script even if one fails
      this.loadMathBoxScriptSequentially(scripts, index + 1);
    };
    this.renderer.appendChild(this.document.body, scriptElement);
  }

  /**
   * Verifies that MathBox is loaded and functions are available
   */
  private verifyMathBoxLoaded() {
    // Give a short delay to ensure scripts are fully initialized
    setTimeout(() => {
      try {
        if (typeof MathBox === 'undefined' || typeof THREE === 'undefined') {
          console.error('MathBox or THREE is not defined after loading scripts');
          this.error = 'Failed to load MathBox library. Please refresh the page.';
          return;
        }

        // Special workaround for OrbitControls
        if (typeof THREE.OrbitControls === 'undefined' && (THREE as any).OrbitControls) {
          // In some cases, the controls are added to the THREE object but not as a property
          // This happens due to how OrbitControls is defined in the script
          THREE.OrbitControls = (THREE as any).OrbitControls;
          console.log('Applied OrbitControls workaround');
        }

        // Mark as loaded
        this.mathboxLoaded = true;
        this.mathboxService.setMathBoxLoaded();
        console.log('MathBox library successfully loaded');
        
        // If we're already on the visual tab, initialize the visualization
        if (this.activeTab === 'visual') {
          setTimeout(() => {
            this.directMathBoxVisualization();
          }, 100);
        }
      } catch (e) {
        console.error('Error verifying MathBox:', e);
        this.error = 'Error initializing MathBox: ' + e;
      }
    }, 500);
  }

  /**
   * Creates/updates the 3D visualization
   */
  visualize() {
    if (!this.mathboxLoaded) {
      this.error = 'MathBox is still loading. Please wait a moment and try again.';
      return;
    }

    if (!this.visualExpression.trim()) {
      this.error = 'Please enter an expression to visualize';
      return;
    }

    // Try our direct visualization approach instead of the service
    this.directMathBoxVisualization();

    // Add to history
    this.history.push({
      type: 'Visualization',
      input: this.visualExpression,
      output: 'Created 3D visualization'
    });
  }

  /**
   * Direct MathBox visualization without going through the service layer
   */
  directMathBoxVisualization() {
    console.log('Attempting direct MathBox visualization');
    
    const container = document.getElementById('mathbox-container');
    if (!container) {
      console.error('Mathbox container not found');
      return;
    }
    
    // Make sure container is visible and has dimensions
    console.log('Container dimensions:', container.offsetWidth, 'x', container.offsetHeight);
    
    if (container.offsetWidth === 0 || container.offsetHeight === 0) {
      console.warn('Container has zero dimensions, setting minimum size');
      container.style.width = '100%';
      container.style.height = '400px';
    }
    
    // Clean up previous visualization if any
    if (this.cleanupVisualization) {
      this.cleanupVisualization();
      this.cleanupVisualization = null;
    }
    
    // Clear container safely
    this.clearContainer(container);
    
    // Test if MathBox is defined in any of the possible ways
    const hasMathBox = typeof MathBox === 'function' || 
                      (typeof window !== 'undefined' && (window as any)['MathBox']) ||
                      (typeof window !== 'undefined' && (window as any)['mathbox']);
    
    try {
      if (!hasMathBox) {
        console.error('MathBox is not available, falling back to THREE.js visualization');
        this.createThreeFunctionVisualization(container);
        return;
      }

      const mathboxFn = typeof MathBox === 'function' ? MathBox : 
                        ((window as any)['MathBox'] || (window as any)['mathbox']);
      
      if (typeof mathboxFn !== 'function' || typeof mathboxFn.mathBox !== 'function') {
        console.error('MathBox function not found correctly, falling back to THREE.js visualization');
        this.createThreeFunctionVisualization(container);
        return;
      }

      // Parse the expression
      const jsExpression = this.convertToJsExpression(this.visualExpression);
      console.log('Converted expression:', jsExpression);
      
      const func = new Function('x', 'y', `return ${jsExpression};`);
      
      // Create MathBox directly
      console.log('Creating MathBox instance');
      const mathbox = mathboxFn.mathBox({
        plugins: ['core', 'controls', 'cursor'],
        controls: {
          klass: typeof THREE !== 'undefined' && THREE.OrbitControls ? THREE.OrbitControls : null
        },
        element: container,
      });
      
      if (!mathbox) {
        console.error('Failed to create MathBox instance');
        this.createThreeFunctionVisualization(container);
        return;
      }

      // Rest of your MathBox code...
      // ...
    } catch (err) {
      console.error('Error in direct MathBox visualization:', err);
      this.error = `Error creating visualization: ${err instanceof Error ? err.message : String(err)}`;
      
      // Fall back to THREE.js visualization
      this.createThreeFunctionVisualization(container);
    }
  }

  /**
   * Converts a math expression to JavaScript
   */
  private convertToJsExpression(expression: string): string {
    return expression
      .replace(/sin\(/g, 'Math.sin(')
      .replace(/cos\(/g, 'Math.cos(')
      .replace(/tan\(/g, 'Math.tan(')
      .replace(/exp\(/g, 'Math.exp(')
      .replace(/sqrt\(/g, 'Math.sqrt(')
      .replace(/log\(/g, 'Math.log(')
      .replace(/abs\(/g, 'Math.abs(')
      .replace(/pi/g, 'Math.PI')
      .replace(/e(?![a-zA-Z])/g, 'Math.E')
      .replace(/\^/g, '**');
  }

  /**
   * Creates a direct THREE.js visualization of the function without using MathBox
   */
  private createThreeFunctionVisualization(container: HTMLElement) {
    console.log('Creating THREE.js function visualization');
    try {
      if (typeof THREE === 'undefined') {
        console.error('THREE is not defined');
        this.renderBasicScene(container);
        return;
      }
      
      // Parse the expression
      const jsExpression = this.convertToJsExpression(this.visualExpression);
      console.log('Converted expression:', jsExpression);
      
      const func = new Function('x', 'y', `return ${jsExpression};`);
      
      // Create renderer
      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(container.offsetWidth, container.offsetHeight);
      container.appendChild(renderer.domElement);
      
      // Create scene
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf0f0f0);
      
      // Create camera
      const camera = new THREE.PerspectiveCamera(
        60, 
        container.offsetWidth / container.offsetHeight, 
        0.1, 
        1000
      );
      camera.position.set(3, 3, 3);
      camera.lookAt(0, 0, 0);
      
      // Add light
      const light = new THREE.DirectionalLight(0xffffff, 1);
      light.position.set(1, 1, 1).normalize();
      scene.add(light);
      
      // Add ambient light for better visibility
      scene.add(new THREE.AmbientLight(0x404040));
      
      // Create grid helper
      const gridHelper = new THREE.GridHelper(10, 10);
      scene.add(gridHelper);
      
      // Create axes helper
      const axesHelper = new THREE.AxesHelper(5);
      scene.add(axesHelper);
      
      // Create function surface
      const range = this.visualRange;
      const resolution = 50; // Grid resolution
      
      // Create geometry
      const geometry = new THREE.BufferGeometry();
      const vertices: number[] = [];
      const indices: number[] = [];
      
      // Create vertices grid
      for (let i = 0; i <= resolution; i++) {
        const x = range[0] + (i / resolution) * (range[1] - range[0]);
        for (let j = 0; j <= resolution; j++) {
          const y = range[0] + (j / resolution) * (range[1] - range[0]);
          let z = 0;
          
          try {
            z = func(x, y);
            if (!isFinite(z)) z = 0;
            // Clamp extreme values
            z = Math.max(Math.min(z, 10), -10);
          } catch (e) {
            console.warn('Function evaluation error:', e);
          }
          
          vertices.push(x, y, z);
        }
      }
      
      // Create indices for triangles
      for (let i = 0; i < resolution; i++) {
        for (let j = 0; j < resolution; j++) {
          const a = i * (resolution + 1) + j;
          const b = i * (resolution + 1) + j + 1;
          const c = (i + 1) * (resolution + 1) + j;
          const d = (i + 1) * (resolution + 1) + j + 1;
          
          // Create two triangles for each grid cell
          indices.push(a, c, b);
          indices.push(c, d, b);
        }
      }
      
      // Set geometry attributes
      geometry.setIndex(indices);
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      geometry.computeVertexNormals();
      
      // Create material
      const material = new THREE.MeshPhongMaterial({
        color: 0x3090FF,
        side: THREE.DoubleSide,
        wireframe: false,
        shininess: 50
      });
      
      // Create mesh
      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);
      
      // Add wireframe
      const wireframe = new THREE.LineSegments(
        new THREE.WireframeGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.2 })
      );
      scene.add(wireframe);
      
      // Add OrbitControls if available
      let controls = null;
      if (THREE.OrbitControls) {
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.25;
      }
      
      // Create animation function
      const animate = () => {
        const animationId = requestAnimationFrame(animate);
        
        // Update controls if available
        if (controls) controls.update();
        
        // Render scene
        renderer.render(scene, camera);
        
        // Store cleanup function
        this.cleanupVisualization = () => {
          console.log('Cleaning up THREE.js function visualization');
          cancelAnimationFrame(animationId);
          
          // Clean up controls
          if (controls) {
            controls.dispose();
          }
          
          // Dispose resources
          if (renderer) renderer.dispose();
          if (geometry) geometry.dispose();
          if (material) material.dispose();
          if (wireframe && wireframe.material) {
            // Fix for THREE.Material issue - use any type instead
            const wireMaterial = wireframe.material as any;
            if (wireMaterial && wireMaterial.dispose) {
              wireMaterial.dispose();
            }
          }
          
          // Safe remove canvas
          if (renderer.domElement.parentNode === container) {
            container.removeChild(renderer.domElement);
          } else {
            this.clearContainer(container);
          }
        };
      };
      
      // Start animation
      animate();
      this.visualizationActive = true;
      console.log('THREE.js function visualization created successfully');
      this.result = 'Visualization created successfully';
      
    } catch (err) {
      console.error('Error creating THREE.js function visualization:', err);
      this.error = `Error creating function visualization: ${err instanceof Error ? err.message : String(err)}`;
      // Fall back to basic scene as last resort
      this.renderBasicScene(container);
    }
  }

  /**
   * Renders a basic THREE.js scene as a fallback
   * @param container The container element
   * @returns True if successful, false otherwise
   */
  private renderBasicScene(container: HTMLElement): boolean {
    console.log('Attempting to render basic THREE.js scene');
    try {
      if (typeof THREE === 'undefined') {
        console.error('THREE is not defined');
        return false;
      }
      
      // Create renderer
      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(container.offsetWidth, container.offsetHeight);
      container.appendChild(renderer.domElement);
      
      // Create scene
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf0f0f0);
      
      // Create camera
      const camera = new THREE.PerspectiveCamera(
        75, 
        container.offsetWidth / container.offsetHeight, 
        0.1, 
        1000
      );
      camera.position.z = 5;
      
      // Add light
      const light = new THREE.DirectionalLight(0xffffff, 1);
      light.position.set(1, 1, 1).normalize();
      scene.add(light);
      
      // Add ambient light
      scene.add(new THREE.AmbientLight(0x404040));
      
      // Create a simple mesh (cube)
      const geometry = new THREE.BoxGeometry(1, 1, 1);
      const material = new THREE.MeshPhongMaterial({ color: 0x3090FF });
      const cube = new THREE.Mesh(geometry, material);
      scene.add(cube);
      
      // Store a reference to the domElement for proper cleanup
      const rendererDomElement = renderer.domElement;
      
      // Create animate function
      const animate = () => {
        const animationId = requestAnimationFrame(animate);
        cube.rotation.x += 0.01;
        cube.rotation.y += 0.01;
        renderer.render(scene, camera);
        
        // Store cleanup function
        this.cleanupVisualization = () => {
          console.log('Cleaning up basic THREE.js scene');
          cancelAnimationFrame(animationId);
          
          // Safely dispose THREE.js resources
          if (renderer) {
            renderer.dispose();
          }
          if (geometry) {
            geometry.dispose();
          }
          if (material) {
            material.dispose();
          }
          
          // Safely remove the canvas element
          try {
            if (rendererDomElement && rendererDomElement.parentNode === container) {
              container.removeChild(rendererDomElement);
            }
          } catch (err) {
            console.error('Error removing renderer DOM element:', err);
            // Fallback to clearing the entire container
            this.clearContainer(container);
          }
        };
      };
      
      // Start animation
      animate();
      this.visualizationActive = true;
      console.log('Basic THREE.js scene rendered successfully');
      return true;
    } catch (err) {
      console.error('Failed to render basic THREE.js scene:', err);
      return false;
    }
  }

  /**
   * Safely clears a container element
   */
  private clearContainer(container: HTMLElement) {
    try {
      // Use a safer approach to clear the container
      container.innerHTML = '';
    } catch (err) {
      console.error('Error clearing container:', err);
    }
  }

  /**
   * Updates the visualization range
   */
  updateRange(min: number, max: number) {
    this.visualRange = [min, max, min, max];
    if (this.activeTab === 'visual' && this.visualExpression) {
      this.visualize();
    }
  }

  /**
   * Loads an example 3D visualization expression
   */
  loadVisualExample(example: string) {
    this.visualExpression = example;
    this.error = '';
    this.result = `Loaded example: ${example}`;
    
    // Automatically visualize when loading an example
    if (this.activeTab === 'visual') {
      this.visualize();
    }
  }

  /**
   * Clean up the visualization when switching tabs
   */
  switchTab(tabName: string) {
    // Clean up 3D visualization if switching away from visual tab
    if (this.activeTab === 'visual' && tabName !== 'visual' && this.cleanupVisualization) {
      this.cleanupVisualization();
      this.cleanupVisualization = null;
    }
    
    // Clean up relation graph if switching away from relations tab
    if (this.activeTab === 'relations' && tabName !== 'relations' && this.cleanupRelationGraph) {
      this.cleanupRelationGraph();
      this.cleanupRelationGraph = null;
    }
    
    this.activeTab = tabName;
    
    // Initialize visualization if switching to visual tab
    if (tabName === 'visual' && this.mathboxLoaded) {
      // Small delay to ensure the container is visible before rendering
      setTimeout(() => {
        this.directMathBoxVisualization();
      }, 100);
    }
    
    // Initialize relation graph if switching to relations tab
    if (tabName === 'relations' && this.sigmaLoaded) {
      setTimeout(() => {
        this.visualizeRelation();
      }, 100);
    }
  }

  /**
   * Load Sigma.js and graphology scripts for graph visualization
   */
  loadSigmaScripts() {
    const scripts = [
      // Dependencies
      'https://unpkg.com/graphology@0.25.1/dist/graphology.umd.min.js',
      'https://unpkg.com/graphology-layout@0.6.1/dist/graphology-layout.min.js',
      'https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js',
      'https://unpkg.com/sigma@latest/dist/sigma.min.js'
    ];
    
    console.log('Loading Sigma.js scripts...');
    this.loadSigmaScriptsSequentially(scripts, 0);
  }
  
  /**
   * Loads Sigma.js scripts sequentially
   */
  private loadSigmaScriptsSequentially(scripts: string[], index: number) {
    if (index >= scripts.length) {
      console.log('All Sigma.js scripts loaded successfully');
      this.verifySigmaLoaded();
      return;
    }
    
    const scriptElement = this.renderer.createElement('script');
    scriptElement.src = scripts[index];
    scriptElement.onload = () => {
      console.log(`Script loaded: ${scripts[index]}`);
      this.loadSigmaScriptsSequentially(scripts, index + 1);
    };
    scriptElement.onerror = (e: Event) => {
      console.error(`Failed to load script: ${scripts[index]}`);
      this.loadSigmaScriptsSequentially(scripts, index + 1);
    };
    this.renderer.appendChild(this.document.body, scriptElement);
  }
  
  /**
   * Verify Sigma.js is loaded
   */
  private verifySigmaLoaded() {
    setTimeout(() => {
      try {
        if (typeof graphology === 'undefined' || typeof Sigma === 'undefined') {
          console.error('Sigma.js or graphology not defined after loading scripts');
          this.sigmaLoaded = false;
          return;
        }
        
        this.sigmaLoaded = true;
        console.log('Sigma.js and graphology loaded successfully');
        
        // Initialize graph if already on relations tab
        if (this.activeTab === 'relations') {
          setTimeout(() => {
            this.visualizeRelation();
          }, 100);
        }
      } catch (e) {
        console.error('Error verifying Sigma.js:', e);
        this.sigmaLoaded = false;
      }
    }, 500);
  }
  
  /**
   * Visualize relations using Sigma.js
   */
  visualizeRelation() {
    if (!this.relationExpression.trim()) {
      this.error = 'Please enter a relation expression';
      return;
    }
    
    this.loading = true;
    this.error = '';
    
    // Clear any existing graph
    if (this.cleanupRelationGraph) {
      this.cleanupRelationGraph();
      this.cleanupRelationGraph = null;
    }
    
    const container = this.document.getElementById('sigma-container');
    if (!container) {
      this.error = 'Graph container not found';
      this.loading = false;
      return;
    }
    
    // Ensure Sigma is loaded
    if (!this.sigmaLoaded || !Sigma || !graphology) {
      this.error = 'Graph libraries not loaded. Please reload and try again.';
      this.loading = false;
      return;
    }
    
    try {
      // Parse relation expression
      const relations = this.parseRelationExpression(this.relationExpression);
      console.log('Parsed relations:', relations);
      
      // Create a new graph
      const graph = new graphology.Graph({ multi: false, type: 'directed' });
      
      // Add nodes and edges based on relations
      this.buildGraphFromRelations(graph, relations);
      
      // Apply the selected layout
      this.applyGraphLayout(graph, this.graphLayout);
      
      // Adjust node sizes based on connections if enabled
      if (this.sizeByConnections) {
        graph.forEachNode((node: string) => {
          const degree = graph.degree(node);
          const scaledSize = Math.max(this.nodeSize, this.nodeSize * (1 + (degree / 2)));
          graph.setNodeAttribute(node, 'size', scaledSize);
        });
      } else {
        // Otherwise, use the fixed node size
        graph.forEachNode((node: string) => {
          graph.setNodeAttribute(node, 'size', this.nodeSize);
        });
      }
      
      // Render the graph
      const renderer = new Sigma(graph, container, {
        renderEdgeLabels: true,
        defaultEdgeType: 'arrow',
        defaultNodeColor: '#6c7fee',
        defaultEdgeColor: '#888',
        labelSize: 14,
        labelColor: '#000',
        edgeLabelSize: 12,
      });
      
      // Add hover interactions
      renderer.on('enterNode', ({ node }: { node: string }) => {
        // Find all connected nodes
        const neighbors = new Set<string>();
        const connectedEdges = [...graph.inEdges(node), ...graph.outEdges(node)];
        
        // Add connected nodes to the neighbors set
        connectedEdges.forEach(edge => {
          const source = graph.source(edge);
          const target = graph.target(edge);
          if (source !== node) neighbors.add(source);
          if (target !== node) neighbors.add(target);
        });
        
        // Highlight the hovered node
        graph.setNodeAttribute(node, 'color', '#ff5500');
        
        // Highlight connected nodes
        neighbors.forEach(neighbor => {
          graph.setNodeAttribute(neighbor, 'color', '#ff9900');
        });
        
        // Highlight connected edges
        connectedEdges.forEach(edge => {
          graph.setEdgeAttribute(edge, 'color', '#ff5500');
          graph.setEdgeAttribute(edge, 'size', 3);
        });
        
        renderer.refresh();
      });
      
      renderer.on('leaveNode', ({ node }: { node: string }) => {
        // Get all connected edges and nodes
        const connectedEdges = [...graph.inEdges(node), ...graph.outEdges(node)];
        const neighbors = new Set<string>();
        
        connectedEdges.forEach(edge => {
          const source = graph.source(edge);
          const target = graph.target(edge);
          if (source !== node) neighbors.add(source);
          if (target !== node) neighbors.add(target);
        });
        
        // Reset node color for the hovered node
        graph.setNodeAttribute(node, 'color', '#6c7fee');
        
        // Reset node colors for connected nodes
        neighbors.forEach(neighbor => {
          graph.setNodeAttribute(neighbor, 'color', '#6c7fee');
        });
        
        // Reset edge colors and sizes
        connectedEdges.forEach(edge => {
          graph.setEdgeAttribute(edge, 'color', '#888');
          graph.setEdgeAttribute(edge, 'size', 2);
        });
        
        renderer.refresh();
      });
      
      // Set up cleanup function
      this.cleanupRelationGraph = () => {
        try {
          renderer.kill();
          while (container.firstChild) {
            container.removeChild(container.firstChild);
          }
        } catch (err) {
          console.error('Error cleaning up graph:', err);
        }
      };
      
      this.relationActive = true;
      
      // Add to history
      this.history.push({
        type: 'Relation Graph',
        input: this.relationExpression,
        output: 'Graph visualization created'
      });
      
    } catch (err) {
      console.error('Error visualizing relation:', err);
      this.error = 'Error visualizing relation: ' + (err instanceof Error ? err.message : String(err));
    } finally {
      this.loading = false;
    }
  }
  
  /**
   * Parse relation expression into an array of relation objects
   */
  private parseRelationExpression(expression: string): Array<{from: string, to: string, bidirectional: boolean}> {
    const relations: Array<{from: string, to: string, bidirectional: boolean}> = [];
    
    // Normalize arrows and split by commas
    const normalizedExpression = expression
      .replace(/->/g, '→')
      .replace(/<->/g, '↔');
    
    const relationParts = normalizedExpression.split(',').map(part => part.trim());
    
    for (const part of relationParts) {
      if (part.includes('→') || part.includes('↔')) {
        // Check for one-to-many: A→{B,C,D}
        const oneToManyMatch = part.match(/(.+?)→\{(.+?)\}/);
        if (oneToManyMatch) {
          const source = oneToManyMatch[1].trim();
          const targets = oneToManyMatch[2].split(',').map(t => t.trim());
          
          for (const target of targets) {
            relations.push({
              from: source,
              to: target,
              bidirectional: false
            });
          }
          continue;
        }
        
        // Check for many-to-one: {A,B,C}→D
        const manyToOneMatch = part.match(/\{(.+?)\}→(.+)/);
        if (manyToOneMatch) {
          const sources = manyToOneMatch[1].split(',').map(s => s.trim());
          const target = manyToOneMatch[2].trim();
          
          for (const source of sources) {
            relations.push({
              from: source,
              to: target,
              bidirectional: false
            });
          }
          continue;
        }
        
        // Handle bidirectional relations: A↔B
        if (part.includes('↔')) {
          const [source, target] = part.split('↔').map(node => node.trim());
          relations.push({
            from: source,
            to: target,
            bidirectional: true
          });
          continue;
        }
        
        // Handle chain: A→B→C→D
        const chain = part.split('→').map(node => node.trim());
        for (let i = 0; i < chain.length - 1; i++) {
          relations.push({
            from: chain[i],
            to: chain[i + 1],
            bidirectional: false
          });
        }
      }
    }
    
    return relations;
  }
  
  /**
   * Build graph from relations
   */
  private buildGraphFromRelations(graph: any, relations: Array<{from: string, to: string, bidirectional: boolean}>) {
    // Set of all node ids
    const nodeIds = new Set<string>();
    
    // Add all nodes first
    for (const relation of relations) {
      nodeIds.add(relation.from);
      nodeIds.add(relation.to);
    }
    
    // Add nodes to graph
    const colors = ['#4285F4', '#EA4335', '#FBBC05', '#34A853', '#8958E8', '#00ACC1'];
    let colorIndex = 0;
    
    nodeIds.forEach(nodeId => {
      // Get a unique color from the palette
      const color = colors[colorIndex % colors.length];
      colorIndex++;
      
      graph.addNode(nodeId, {
        label: nodeId,
        size: this.nodeSize,
        color: color
      });
    });
    
    // Add edges
    for (const relation of relations) {
      // Add the edge
      const edgeId = `${relation.from}-${relation.to}`;
      if (!graph.hasEdge(relation.from, relation.to)) {
        graph.addEdge(relation.from, relation.to, {
          id: edgeId,
          label: relation.bidirectional ? '↔' : '→',
          color: '#999',
          type: 'arrow'
        });
      }
      
      // Add reverse edge if bidirectional
      if (relation.bidirectional && !graph.hasEdge(relation.to, relation.from)) {
        const reverseEdgeId = `${relation.to}-${relation.from}`;
        graph.addEdge(relation.to, relation.from, {
          id: reverseEdgeId,
          label: '↔',
          color: '#999',
          type: 'arrow'
        });
      }
    }
  }
  
  /**
   * Apply layout to the graph
   */
  private applyGraphLayout(graph: any, layoutType: string) {
    switch (layoutType) {
      case 'force':
        // Apply force-directed layout
        const settings = {
          iterations: 100,
          gravity: 0.1,
          theta: 0.5,
          ejectFactor: 0.2
        };
        
        if (typeof layoutForce !== 'undefined') {
          const positions = layoutForce(graph, settings);
          // Scale positions
          Object.keys(positions).forEach(node => {
            graph.setNodeAttribute(node, 'x', positions[node].x * 100);
            graph.setNodeAttribute(node, 'y', positions[node].y * 100);
          });
        } else {
          // Fallback to random layout
          for (const node of graph.nodes()) {
            graph.setNodeAttribute(node, 'x', Math.random() * 100);
            graph.setNodeAttribute(node, 'y', Math.random() * 100);
          }
        }
        break;
        
      case 'circular':
        if (typeof layoutCircular !== 'undefined') {
          layoutCircular.assign(graph);
          // Scale positions
          for (const node of graph.nodes()) {
            const x = graph.getNodeAttribute(node, 'x');
            const y = graph.getNodeAttribute(node, 'y');
            graph.setNodeAttribute(node, 'x', x * 100);
            graph.setNodeAttribute(node, 'y', y * 100);
          }
        } else {
          // Fallback: place nodes in a circle manually
          const nodeCount = graph.order;
          const radius = 100;
          let i = 0;
          
          for (const node of graph.nodes()) {
            const angle = (2 * Math.PI * i) / nodeCount;
            graph.setNodeAttribute(node, 'x', radius * Math.cos(angle));
            graph.setNodeAttribute(node, 'y', radius * Math.sin(angle));
            i++;
          }
        }
        break;
        
      case 'tree':
        if (typeof layoutTree !== 'undefined') {
          layoutTree.assign(graph, {
            hierarchyMode: 'directed'
          });
          // Scale positions
          for (const node of graph.nodes()) {
            const x = graph.getNodeAttribute(node, 'x');
            const y = graph.getNodeAttribute(node, 'y');
            graph.setNodeAttribute(node, 'x', x * 100);
            graph.setNodeAttribute(node, 'y', y * 100);
          }
        } else {
          // Fallback to simple tree layout
          const layers: {[key: string]: number} = {};
          const visited = new Set<string>();
          
          // Find root nodes (those with no incoming edges)
          const rootNodes = [];
          for (const node of graph.nodes()) {
            if (graph.inDegree(node) === 0) {
              rootNodes.push(node);
              layers[node] = 0;
            }
          }
          
          // If no root nodes found, use the first node
          if (rootNodes.length === 0 && graph.order > 0) {
            const firstNode = graph.nodes()[0];
            rootNodes.push(firstNode);
            layers[firstNode] = 0;
          }
          
          // Perform BFS to assign layers
          const queue: string[] = [...rootNodes];
          while (queue.length > 0) {
            const node = queue.shift()!;
            visited.add(node);
            const layer = layers[node];
            
            for (const neighbor of graph.outNeighbors(node)) {
              if (!visited.has(neighbor)) {
                layers[neighbor] = layer + 1;
                queue.push(neighbor);
              }
            }
          }
          
          // Count nodes per layer
          const nodeCounts: {[key: number]: number} = {};
          const nodePositions: {[key: number]: number[]} = {};
          
          for (const node in layers) {
            const layer = layers[node];
            nodeCounts[layer] = (nodeCounts[layer] || 0) + 1;
            if (!nodePositions[layer]) {
              nodePositions[layer] = [];
            }
          }
          
          // Assign positions
          for (const node in layers) {
            const layer = layers[node];
            const count = nodeCounts[layer];
            const position = nodePositions[layer].length;
            const x = count > 1 ? (position / (count - 1)) * 200 - 100 : 0;
            const y = layer * 100;
            
            graph.setNodeAttribute(node, 'x', x);
            graph.setNodeAttribute(node, 'y', y);
            nodePositions[layer].push(position + 1);
          }
        }
        break;
        
      case 'grid':
        if (typeof layoutGrid !== 'undefined') {
          layoutGrid.assign(graph);
          // Scale positions
          for (const node of graph.nodes()) {
            const x = graph.getNodeAttribute(node, 'x');
            const y = graph.getNodeAttribute(node, 'y');
            graph.setNodeAttribute(node, 'x', x * 100);
            graph.setNodeAttribute(node, 'y', y * 100);
          }
        } else {
          // Fallback: arrange nodes in a grid manually
          const nodeCount = graph.order;
          const cols = Math.ceil(Math.sqrt(nodeCount));
          let row = 0;
          let col = 0;
          
          for (const node of graph.nodes()) {
            graph.setNodeAttribute(node, 'x', (col - cols / 2) * 50);
            graph.setNodeAttribute(node, 'y', (row - Math.ceil(nodeCount / cols) / 2) * 50);
            
            col++;
            if (col >= cols) {
              col = 0;
              row++;
            }
          }
        }
        break;
        
      default:
        // Random layout as fallback
        for (const node of graph.nodes()) {
          graph.setNodeAttribute(node, 'x', Math.random() * 100);
          graph.setNodeAttribute(node, 'y', Math.random() * 100);
        }
    }
  }
  
  /**
   * Load a relation example
   */
  loadRelationExample(example: string) {
    this.relationExpression = example;
    this.error = '';
    this.result = `Loaded example: ${example}`;
    
    if (this.activeTab === 'relations' && this.sigmaLoaded) {
      this.visualizeRelation();
    }
  }

  /**
   * Integrates the expression
   */
  integrate() {
    if (!this.nerdamerLoaded) {
      this.error = 'Nerdamer is still loading. Please wait a moment and try again.';
      // Try to reload scripts if they failed previously
      this.reloadNerdamerIfNeeded();
      return;
    }

    if (!this.calcExpression.trim()) {
      this.error = 'Please enter an expression to integrate';
      return;
    }

    try {
      const result = this.calculusService.integrate(this.calcExpression, this.calcVariable);
      this.calcResult = result.result;
      this.calcLatex = result.latex;
      this.error = '';
      this.result = 'Integration successful';

      // Add to history
      this.history.push({
        type: 'Integration',
        input: `∫(${this.calcExpression}) d${this.calcVariable}`,
        output: this.calcResult
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      console.error('Integration error:', errMsg);
      
      // Provide more targeted help based on the error
      if (errMsg.includes('is not a function') || errMsg.includes('not available')) {
        this.error = 'Nerdamer integration feature not properly loaded. Try refreshing the page.';
        // Try to reload Nerdamer
        this.reloadNerdamerIfNeeded();
      } else {
        this.error = `Error performing integration: ${errMsg}`;
      }
    }
  }

  /**
   * Tries to reload Nerdamer if it appears to be not working properly
   */
  public reloadNerdamerIfNeeded() {
    if (!this.nerdamerLoaded || this.error.includes('not a function') || this.error.includes('not available')) {
      console.log('Attempting to reload Nerdamer scripts...');
      this.loadNerdamerScripts();
    }
  }

  /**
   * Differentiates the expression
   */
  differentiate() {
    if (!this.nerdamerLoaded) {
      this.error = 'Nerdamer is still loading. Please wait a moment and try again.';
      // Try to reload scripts if they failed previously
      this.reloadNerdamerIfNeeded();
      return;
    }

    if (!this.calcExpression.trim()) {
      this.error = 'Please enter an expression to differentiate';
      return;
    }

    try {
      const result = this.calculusService.differentiate(this.calcExpression, this.calcVariable);
      this.calcResult = result.result;
      this.calcLatex = result.latex;
      this.error = '';
      this.result = 'Differentiation successful';

      // Add to history
      this.history.push({
        type: 'Differentiation',
        input: `d/d${this.calcVariable}(${this.calcExpression})`,
        output: this.calcResult
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      console.error('Differentiation error:', errMsg);
      
      // Provide more targeted help based on the error
      if (errMsg.includes('is not a function') || errMsg.includes('not available')) {
        this.error = 'Nerdamer differentiation feature not properly loaded. Try refreshing the page.';
        // Try to reload Nerdamer
        this.reloadNerdamerIfNeeded();
      } else {
        this.error = `Error performing differentiation: ${errMsg}`;
      }
    }
  }

  /**
   * Simplifies the expression
   */
  simplify() {
    if (!this.nerdamerLoaded) {
      this.error = 'Nerdamer is still loading. Please wait a moment and try again.';
      // Try to reload scripts if they failed previously
      this.reloadNerdamerIfNeeded();
      return;
    }

    if (!this.calcExpression.trim()) {
      this.error = 'Please enter an expression to simplify';
      return;
    }

    try {
      const result = this.calculusService.simplify(this.calcExpression);
      this.calcResult = result.result;
      this.calcLatex = result.latex;
      this.error = '';
      this.result = 'Simplification successful';

      // Add to history
      this.history.push({
        type: 'Simplification',
        input: this.calcExpression,
        output: this.calcResult
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      console.error('Simplification error:', errMsg);
      
      // Provide more targeted help based on the error
      if (errMsg.includes('is not a function') || errMsg.includes('not available')) {
        this.error = 'Nerdamer simplification feature not properly loaded. Try refreshing the page.';
        // Try to reload Nerdamer
        this.reloadNerdamerIfNeeded();
      } else {
        this.error = `Error simplifying expression: ${errMsg}`;
      }
    }
  }

  /**
   * Expands the expression
   */
  expand() {
    if (!this.nerdamerLoaded) {
      this.error = 'Nerdamer is still loading. Please wait a moment and try again.';
      // Try to reload scripts if they failed previously
      this.reloadNerdamerIfNeeded();
      return;
    }

    if (!this.calcExpression.trim()) {
      this.error = 'Please enter an expression to expand';
      return;
    }

    try {
      const result = this.calculusService.expand(this.calcExpression);
      this.calcResult = result.result;
      this.calcLatex = result.latex;
      this.error = '';
      this.result = 'Expansion successful';

      // Add to history
      this.history.push({
        type: 'Expansion',
        input: this.calcExpression,
        output: this.calcResult
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      console.error('Expansion error:', errMsg);
      
      // Provide more targeted help based on the error
      if (errMsg.includes('is not a function') || errMsg.includes('not available')) {
        this.error = 'Nerdamer expansion feature not properly loaded. Try refreshing the page.';
        // Try to reload Nerdamer
        this.reloadNerdamerIfNeeded();
      } else {
        this.error = `Error expanding expression: ${errMsg}`;
      }
    }
  }

  /**
   * Loads an example calculus expression
   */
  loadCalcExample(example: string) {
    this.calcExpression = example;
    this.error = '';
    this.result = `Loaded example: ${example}`;
    
    // Check if Nerdamer is loaded
    this.checkNerdamerStatus();
  }
  
  /**
   * Checks the status of Nerdamer and provides feedback to the user
   * @returns True if Nerdamer is properly loaded
   */
  private checkNerdamerStatus(): boolean {
    // If nerdamer is marked as loaded in our component, check if it actually exists
    if (this.nerdamerLoaded) {
      if (typeof nerdamer === 'undefined') {
        console.error('Nerdamer marked as loaded but is undefined');
        this.nerdamerLoaded = false;
        this.error = 'Nerdamer library not properly loaded. Attempting to reload...';
        this.reloadNerdamerIfNeeded();
        return false;
      }
      return true;
    } else {
      // Not loaded, give a helpful message
      this.error = 'Nerdamer is still loading. Please wait a moment before using operations.';
      return false;
    }
  }

  /**
   * Handles the range change event from the UI
   * @param event The change event
   */
  public handleRangeChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    if (target && target.value) {
      const values = target.value.split(',');
      if (values.length === 2) {
        const min = parseFloat(values[0]);
        const max = parseFloat(values[1]);
        this.updateRange(min, max);
      }
    }
  }

  // Extract relations from text using the backend API
  extractRelations() {
    if (!this.relationExtractionText.trim()) {
      this.error = 'Please enter text to extract relations';
      return;
    }
    
    this.loading = true;
    this.error = '';
    
    this.z3Service.extractRelations(this.relationExtractionText).subscribe({
      next: (response: { relations: Array<{subject: string, relation: string, object: string}>, method: string }) => {
        // Initialize useAsPremise property for each relation
        this.extractedRelations = response.relations.map(rel => ({
          ...rel,
          useAsPremise: false
        }));
        
        this.extractionMethod = response.method;
        this.loading = false;
        this.selectedConclusionIndex = null; // Reset conclusion selection
        
        // Add to history
        this.history.push({
          type: 'RelationExtraction',
          input: this.relationExtractionText,
          output: `Extracted ${this.extractedRelations.length} relations using ${this.extractionMethod}`
        });
      },
      error: (err: any) => {
        this.error = err.error?.message || 'Error extracting relations';
        this.loading = false;
      }
    });
  }

  // Visualize extracted relations in the relation graph tab
  visualizeExtractedRelations() {
    if (!this.extractedRelations || this.extractedRelations.length === 0) {
      this.error = 'No relations to visualize';
      return;
    }
    
    // Build relation expression from extracted relations
    let relationExpr = '';
    
    // Convert relations to the format used by the relation graph visualization
    for (const relation of this.extractedRelations) {
      if (relationExpr) relationExpr += ', ';
      relationExpr += `${relation.subject}→${relation.object}`;
    }
    
    // Set the relation expression and switch to relation tab
    this.relationExpression = relationExpr;
    this.switchTab('relations');
    
    // Trigger visualization with a slight delay to ensure tab is rendered
    setTimeout(() => {
      this.visualizeRelation();
    }, 100);
  }

  // Add a new empty relation to the list
  addRelation() {
    if (!this.extractedRelations) {
      this.extractedRelations = [];
    }
    
    this.extractedRelations.push({
      subject: '',
      relation: '',
      object: '',
      useAsPremise: false
    });
  }

  // Remove a relation from the list
  removeRelation(index: number) {
    if (index >= 0 && index < this.extractedRelations.length) {
      this.extractedRelations.splice(index, 1);
    }
  }

  // Update relations after manual edits
  updateExtractedRelations() {
    // Filter out any relations with empty fields
    this.extractedRelations = this.extractedRelations.filter(
      rel => rel.subject.trim() && rel.relation.trim() && rel.object.trim()
    );
    
    // Show confirmation message
    this.result = `Relations updated: ${this.extractedRelations.length} valid relations`;
    
    // Update the history
    if (this.extractedRelations.length > 0) {
      this.history.push({
        type: 'RelationEdit',
        input: 'Manual relation editing',
        output: `Updated ${this.extractedRelations.length} relations`
      });
    }
  }

  // Get the selected premises from extracted relations
  getSelectedPremises(): Array<{subject: string, relation: string, object: string}> {
    if (!this.extractedRelations) return [];
    return this.extractedRelations.filter(rel => rel.useAsPremise);
  }
  
  // Get the selected conclusion from extracted relations
  getSelectedConclusion(): {subject: string, relation: string, object: string} | null {
    if (this.selectedConclusionIndex === null || !this.extractedRelations ||
        this.selectedConclusionIndex >= this.extractedRelations.length) {
      return null;
    }
    return this.extractedRelations[this.selectedConclusionIndex];
  }
  
  // Check if relations can be converted to logical statements
  canConvertRelations(): boolean {
    return this.getSelectedPremises().length > 0 && this.getSelectedConclusion() !== null;
  }
  
  // Convert selected relations to logical statements for the theorem prover
  convertRelationsToLogic(): void {
    const premises = this.getSelectedPremises();
    const conclusion = this.getSelectedConclusion();
    
    if (!premises.length || !conclusion) {
      this.error = 'Please select at least one premise and one conclusion';
      return;
    }
    
    // Clear existing natural language premises and conclusion
    this.naturalPremises = [];
    this.naturalConclusion = '';
    
    // Convert each selected premise to a natural language statement
    premises.forEach(premise => {
      const statement = `${premise.subject} ${premise.relation} ${premise.object}`;
      this.naturalPremises.push(statement);
    });
    
    // Set the conclusion
    this.naturalConclusion = `${conclusion.subject} ${conclusion.relation} ${conclusion.object}`;
    
    // Add to history
    this.history.push({
      type: 'RelationToLogic',
      input: `${premises.length} premises and 1 conclusion from relations`,
      output: 'Converted relations to logical statements'
    });
    
    // Show success message
    this.result = 'Relations converted to logical statements. You can now use the Convert to Logic button.';
  }

  // Auto-select all relations as premises except the selected conclusion
  autoSelectPremises(): void {
    if (!this.extractedRelations || this.extractedRelations.length === 0) {
      return;
    }
    
    // Mark all relations as premises
    this.extractedRelations.forEach((relation, index) => {
      // Skip the selected conclusion
      if (this.selectedConclusionIndex !== index) {
        relation.useAsPremise = true;
      }
    });
    
    this.result = 'Auto-selected relations as premises';
  }

  // Save extracted relations to Neo4j database
  saveRelationsToNeo4j() {
    if (!this.extractedRelations || this.extractedRelations.length === 0) {
      this.error = 'No relations to save';
      return;
    }
    
    const relations = this.extractedRelations.map(rel => {
      return {
        source_node: {
          label: 'Entity',
          props: { name: rel.subject }
        },
        target_node: {
          label: 'Entity',
          props: { name: rel.object }
        },
        relation_type: rel.relation
      };
    });
    
    // Send the relations to the Neo4j API - Use direct endpoint
    this.http.post(`${this.neo4jApiUrl}/save_relations`, relations).subscribe({
      next: (response: any) => {
        if (response.success) {
          this.result = `Successfully saved ${response.success_count} relations to Neo4j`;
        } else {
          this.result = 'Failed to save relations';
        }
        
        this.addToHistory('neo4j-save', JSON.stringify(relations), this.result);
      },
      error: (error) => {
        this.error = `Error saving relations: ${error.message || error}`;
        console.error('Neo4j save error:', error);
      }
    });
  }

  findRelatedRelations() {
    if (!this.neo4jSearchQuery) {
      this.error = 'Please enter a search query';
      return;
    }
    
    // Send the search query to the Neo4j API
    this.http.get(`${this.neo4jApiUrl}/find_relations`, {
      params: { query: this.neo4jSearchQuery }
    }).subscribe({
      next: (response: any) => {
        if (response.relations && Array.isArray(response.relations)) {
          this.relatedRelations = response.relations.map((rel: any) => {
            return {
              subject: rel.source || rel.subject,
              relation: rel.relation_type || rel.relation,
              object: rel.target || rel.object
            };
          });
          
          if (this.relatedRelations.length === 0) {
            this.result = 'No related relations found';
          } else {
            this.result = `Found ${this.relatedRelations.length} related relations`;
          }
        } else {
          this.relatedRelations = [];
          this.result = 'No related relations found';
        }
        
        this.addToHistory('neo4j-search', this.neo4jSearchQuery, this.result);
      },
      error: (error) => {
        this.error = `Error finding related relations: ${error.message || error}`;
        console.error('Neo4j search error:', error);
        this.relatedRelations = [];
      }
    });
  }
  
  // Use a found relation in the current relation list
  useFoundRelation(relation: {subject: string, relation: string, object: string}) {
    if (!relation) return;
    
    // Add the relation to the extracted relations
    this.extractedRelations.push({
      subject: relation.subject,
      relation: relation.relation,
      object: relation.object,
      useAsPremise: true
    });
    
    // Update the UI
    this.result = `Added relation: ${relation.subject} ${relation.relation} ${relation.object}`;
  }
  
  // Helper method to add items to history
  private addToHistory(type: string, input: string, output: string, renderedInput?: string) {
    this.history.unshift({
      type,
      input,
      output,
      renderedInput
    });
    
    // Limit history size to avoid performance issues
    if (this.history.length > 50) {
      this.history = this.history.slice(0, 50);
    }
  }

  // Save extracted relations to MongoDB database
  saveRelationsToMongoDB() {
    if (!this.extractedRelations || this.extractedRelations.length === 0) {
      this.error = 'No relations to save';
      return;
    }
    
    const relations = this.extractedRelations.map(rel => {
      return {
        source_node: {
          label: 'Entity',
          props: { name: rel.subject }
        },
        target_node: {
          label: 'Entity',
          props: { name: rel.object }
        },
        relation_type: rel.relation
      };
    });
    
    // Send the relations to the MongoDB API - Use direct endpoint
    this.http.post(`${this.mongodbApiUrl}/save_relations`, relations).subscribe({
      next: (response: any) => {
        if (response.success) {
          this.result = `Successfully saved ${response.success_count} relations to MongoDB`;
        } else {
          this.result = 'Failed to save relations';
        }
        
        this.addToHistory('mongodb-save', JSON.stringify(relations), this.result);
      },
      error: (error) => {
        this.error = `Error saving relations: ${error.message || error}`;
        console.error('MongoDB save error:', error);
      }
    });
  }

  findRelatedRelationsMongoDB() {
    if (!this.neo4jSearchQuery) {
      this.error = 'Please enter a search query';
      return;
    }
    
    // Send the search query to the MongoDB API
    this.http.get(`${this.mongodbApiUrl}/mongodb/find_relations`, {
      params: { query: this.neo4jSearchQuery }
    }).subscribe({
      next: (response: any) => {
        if (response.relations && Array.isArray(response.relations)) {
          this.relatedRelations = response.relations.map((rel: any) => {
            return {
              subject: rel.source || rel.subject,
              relation: rel.relation_type || rel.relation,
              object: rel.target || rel.object
            };
          });
          
          if (this.relatedRelations.length === 0) {
            this.result = 'No related relations found';
          } else {
            this.result = `Found ${this.relatedRelations.length} related relations`;
          }
        } else {
          this.relatedRelations = [];
          this.result = 'No related relations found';
        }
        
        this.addToHistory('mongodb-search', this.neo4jSearchQuery, this.result);
      },
      error: (error) => {
        this.error = `Error finding related relations: ${error.message || error}`;
        console.error('MongoDB search error:', error);
        this.relatedRelations = [];
      }
    });
  }
} 