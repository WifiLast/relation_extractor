import { Injectable } from '@angular/core';
declare var nerdamer: any;

@Injectable({
  providedIn: 'root'
})
export class CalculusService {
  private nerdamerLoaded = false;

  constructor() {
    this.loadNerdamer();
  }

  private loadNerdamer() {
    // Check if nerdamer is already available
    if (typeof nerdamer !== 'undefined') {
      // Verify that it's initialized properly
      if (typeof nerdamer === 'function' || 
          typeof nerdamer.integrate === 'function' || 
          typeof nerdamer.diff === 'function') {
        console.log('Nerdamer detected as already loaded');
        this.nerdamerLoaded = true;
      } else {
        console.warn('Nerdamer object detected but core functionality appears to be missing');
      }
      return;
    }

    // We'll handle the actual script loading in the component
    // since this is a service and doesn't have direct access to the DOM
    console.log('Nerdamer not yet loaded, waiting for component to initialize it');
  }

  /**
   * Integrates a mathematical expression with respect to a variable
   * @param expression The expression to integrate
   * @param variable The variable to integrate with respect to
   * @returns The integrated expression
   */
  integrate(expression: string, variable: string = 'x'): { result: string, latex: string } {
    if (!this.nerdamerLoaded) {
      throw new Error('Nerdamer is not loaded');
    }

    try {
      // Check if the integrate function exists directly or as part of the core object
      let result;
      if (typeof nerdamer.integrate === 'function') {
        result = nerdamer.integrate(expression, variable);
      } else if (typeof nerdamer === 'function') {
        // Try using the alternative syntax where nerdamer is called as a function first
        result = nerdamer(expression).integrate(variable);
      } else {
        throw new Error('Nerdamer integration functionality is not available');
      }

      return {
        result: result.toString(),
        latex: result.toTeX()
      };
    } catch (error) {
      throw new Error(`Error integrating expression: ${error}`);
    }
  }

  /**
   * Differentiates a mathematical expression with respect to a variable
   * @param expression The expression to differentiate
   * @param variable The variable to differentiate with respect to
   * @returns The differentiated expression
   */
  differentiate(expression: string, variable: string = 'x'): { result: string, latex: string } {
    if (!this.nerdamerLoaded) {
      throw new Error('Nerdamer is not loaded');
    }

    try {
      // Check if the diff function exists directly or as part of the core object
      let result;
      if (typeof nerdamer.diff === 'function') {
        result = nerdamer.diff(expression, variable);
      } else if (typeof nerdamer === 'function') {
        // Try using the alternative syntax where nerdamer is called as a function first
        result = nerdamer(expression).diff(variable);
      } else {
        throw new Error('Nerdamer differentiation functionality is not available');
      }

      return {
        result: result.toString(),
        latex: result.toTeX()
      };
    } catch (error) {
      throw new Error(`Error differentiating expression: ${error}`);
    }
  }

  /**
   * Simplifies a mathematical expression
   * @param expression The expression to simplify
   * @returns The simplified expression
   */
  simplify(expression: string): { result: string, latex: string } {
    if (!this.nerdamerLoaded) {
      throw new Error('Nerdamer is not loaded');
    }

    try {
      // Ensure we're using the function form of nerdamer
      if (typeof nerdamer !== 'function') {
        throw new Error('Nerdamer core functionality is not available');
      }
      
      const result = nerdamer(expression).simplify();
      return {
        result: result.toString(),
        latex: result.toTeX()
      };
    } catch (error) {
      throw new Error(`Error simplifying expression: ${error}`);
    }
  }

  /**
   * Expands a mathematical expression
   * @param expression The expression to expand
   * @returns The expanded expression
   */
  expand(expression: string): { result: string, latex: string } {
    if (!this.nerdamerLoaded) {
      throw new Error('Nerdamer is not loaded');
    }

    try {
      // Ensure we're using the function form of nerdamer
      if (typeof nerdamer !== 'function') {
        throw new Error('Nerdamer core functionality is not available');
      }
      
      const result = nerdamer(expression).expand();
      return {
        result: result.toString(),
        latex: result.toTeX()
      };
    } catch (error) {
      throw new Error(`Error expanding expression: ${error}`);
    }
  }

  /**
   * Sets the nerdamerLoaded flag to true (called from component after loading scripts)
   */
  setNerdamerLoaded() {
    this.nerdamerLoaded = true;
  }

  /**
   * Checks if nerdamer is loaded
   */
  isNerdamerLoaded(): boolean {
    return this.nerdamerLoaded;
  }
} 