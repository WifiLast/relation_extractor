import { Injectable } from '@angular/core';

declare var MathBox: any;
declare var THREE: any;

@Injectable({
  providedIn: 'root'
})
export class MathBoxService {
  private mathboxLoaded = false;

  constructor() {
    this.checkMathBox();
  }

  /**
   * Checks if MathBox is already loaded
   */
  private checkMathBox() {
    if (typeof MathBox !== 'undefined' && typeof THREE !== 'undefined') {
      this.mathboxLoaded = true;
      console.log('MathBox detected as already loaded');
    }
  }

  /**
   * Sets the mathboxLoaded flag to true
   */
  setMathBoxLoaded() {
    this.mathboxLoaded = true;
  }

  /**
   * Checks if MathBox is loaded
   */
  isMathBoxLoaded(): boolean {
    return this.mathboxLoaded;
  }

  /**
   * Creates a 3D visualization for a mathematical function
   * @param containerId The ID of the container element
   * @param expression The expression to visualize
   * @param range The range for x and y axes as [xMin, xMax, yMin, yMax]
   * @returns A cleanup function to dispose of resources
   */
  visualizeFunction(containerId: string, expression: string, range: number[] = [-5, 5, -5, 5]): () => void {
    if (!this.mathboxLoaded) {
      throw new Error('MathBox is not loaded');
    }

    // Find the container
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Container with ID ${containerId} not found`);
    }

    // Safely clear the container first
    this.clearContainer(container);

    try {
      // Parse the expression into a JavaScript function
      const func = this.createFunction(expression);

      // Create config for MathBox based on THREE availability
      const config: any = {
        plugins: ['core', 'controls', 'cursor'],
        controls: {
          klass: typeof THREE !== 'undefined' && THREE.OrbitControls ? THREE.OrbitControls : null
        }
      };

      try {
        // Create MathBox instance
        const mathbox = MathBox.mathBox(config);
        
        // Get the underlying THREE.js instance
        const three = mathbox.three;

        // Set the background color
        if (three && three.renderer) {
          three.renderer.setClearColor(new THREE.Color(0xfafafa), 1.0);
        }

        // Create a view
        const view = mathbox.cartesian({
          range: [range[0], range[1], range[0], range[1], [-3, 3]],
          scale: [1, 1, 1]
        });

        // Add axes
        view.axis({
          width: 3,
          axis: 1,
          color: 0x707070
        });
        
        view.axis({
          width: 3,
          axis: 2,
          color: 0x707070
        });
        
        view.axis({
          width: 3,
          axis: 3,
          color: 0x707070
        });

        // Add a grid
        view.grid({
          width: 2,
          divideX: 10,
          divideY: 10,
          opacity: 0.5,
          axes: [1, 3],
          color: 0xd0d0d0
        });

        // Add a function plot for z = f(x,y)
        // First, create a cartesian area to sample the function over
        view.area({
          id: 'sampler',
          width: 64,
          height: 64,
          axes: [1, 2],
          expr: (emit: (x: number, y: number, z: number) => void, x: number, y: number) => {
            try {
              const z = func(x, y);
              emit(x, y, isFinite(z) ? z : 0);
            } catch (e) {
              emit(x, y, 0);
            }
          }
        });

        // Then, create a nice looking surface from the data
        view.surface({
          points: '#sampler',
          shaded: true,
          lineX: true,
          lineY: true,
          color: 0x3090FF,
          opacity: 0.8
        });

        // Return a cleanup function
        return () => {
          console.log('Cleaning up MathBox visualization');
          try {
            // Dispose of resources when done
            if (three && three.renderer) {
              three.renderer.dispose();
            }
            
            // Safely clear the container
            this.clearContainer(container);
          } catch (err) {
            console.error('Error during MathBox cleanup:', err);
          }
        };
      } catch (err) {
        console.error('Error creating visualization with OrbitControls, falling back to simple mode:', err);
        return this.createFallbackVisualization(containerId, expression, range, func);
      }
    } catch (error) {
      throw new Error(`Error visualizing function: ${error}`);
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
   * Creates a fallback visualization without using OrbitControls
   * @param containerId The container ID
   * @param expression The expression being visualized
   * @param range The range for axes
   * @param func The parsed function
   * @returns A cleanup function
   */
  private createFallbackVisualization(
    containerId: string, 
    expression: string, 
    range: number[], 
    func: (x: number, y: number) => number
  ): () => void {
    const container = document.getElementById(containerId);
    if (!container) {
      return () => {};
    }

    try {
      // Safely clear container
      this.clearContainer(container);

      // Create a simpler MathBox instance without controls
      const mathbox = MathBox.mathBox({
        plugins: ['core'],
        controls: null
      });

      const three = mathbox.three;
      if (three && three.renderer) {
        three.renderer.setClearColor(new THREE.Color(0xfafafa), 1.0);
      }

      // Create a static view
      const view = mathbox.cartesian({
        range: [range[0], range[1], range[0], range[1], [-3, 3]],
        scale: [1, 1, 1]
      });

      // Add grid and axes with minimal configuration
      view.grid({
        width: 1,
        opacity: 0.5,
        axes: [1, 3]
      });

      view.axis({ axis: 1 });
      view.axis({ axis: 2 });
      view.axis({ axis: 3 });

      // Create a surface using area sampling
      view.area({
        id: 'sampler',
        width: 32, // Lower resolution for better performance
        height: 32,
        axes: [1, 2],
        expr: (emit: (x: number, y: number, z: number) => void, x: number, y: number) => {
          try {
            const z = func(x, y);
            emit(x, y, isFinite(z) ? z : 0);
          } catch (e) {
            emit(x, y, 0);
          }
        }
      });

      // Create the surface from the sampler
      view.surface({
        points: '#sampler',
        shaded: true,
        color: 0x3090FF,
        opacity: 0.8
      });

      // Add a message to the container about fallback mode
      const messageDiv = document.createElement('div');
      messageDiv.style.position = 'absolute';
      messageDiv.style.bottom = '10px';
      messageDiv.style.left = '10px';
      messageDiv.style.background = 'rgba(255,255,255,0.7)';
      messageDiv.style.padding = '5px';
      messageDiv.style.borderRadius = '3px';
      messageDiv.style.fontSize = '12px';
      messageDiv.style.color = '#333';
      messageDiv.innerText = 'Running in fallback mode (no rotation controls)';
      container.appendChild(messageDiv);

      return () => {
        console.log('Cleaning up fallback visualization');
        try {
          if (three && three.renderer) {
            three.renderer.dispose();
          }
          
          // Safely clear the container
          this.clearContainer(container);
        } catch (e) {
          console.error('Error during fallback cleanup:', e);
        }
      };
    } catch (e) {
      console.error('Even fallback visualization failed:', e);
      
      // Last resort - show error in container
      if (container) {
        container.innerHTML = `
          <div style="padding: 20px; text-align: center;">
            <h3>Visualization Error</h3>
            <p>Could not create 3D visualization for: ${expression}</p>
            <p>Error: ${e}</p>
            <p>Try refreshing the page or using a different browser.</p>
          </div>
        `;
      }
      
      return () => {
        if (container) {
          container.innerHTML = '';
        }
      };
    }
  }

  /**
   * Creates a JavaScript function from a math expression string
   * @param expression The expression to convert
   * @returns A function that takes x and y parameters
   */
  private createFunction(expression: string): (x: number, y: number) => number {
    // Replace common math notation with JavaScript equivalents
    const jsExpression = expression
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

    try {
      // Create a new function that takes x and y parameters
      return new Function('x', 'y', `return ${jsExpression};`) as (x: number, y: number) => number;
    } catch (e) {
      throw new Error(`Invalid expression: ${expression}`);
    }
  }

  /**
   * Calculates surface data for the 3D visualization
   * @param func The function to evaluate
   * @param range The range for x and y axes
   * @param size The grid size
   * @returns A 2D array of z-values
   */
  private calculateSurfaceData(
    func: (x: number, y: number) => number,
    range: number[],
    size: number
  ): number[][][] {
    const [xMin, xMax, yMin, yMax] = range;
    const data: number[][][] = [];

    try {
      // Create a 2D array of points
      for (let i = 0; i < size; i++) {
        const row: number[][] = [];
        const x = xMin + (i / (size - 1)) * (xMax - xMin);
        
        for (let j = 0; j < size; j++) {
          const y = yMin + (j / (size - 1)) * (yMax - yMin);
          try {
            const z = func(x, y);
            // Handle NaN or infinity values
            row.push([x, y, isFinite(z) ? z : 0]);
          } catch (e) {
            row.push([x, y, 0]);
          }
        }
        data.push(row);
      }
      
      return data;
    } catch (e) {
      throw new Error(`Error calculating surface data: ${e}`);
    }
  }
} 