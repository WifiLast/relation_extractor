declare module 'nerdamer' {
  interface NerdamerResult {
    text(option?: string): string;
    toString(): string;
    toTeX(): string;
    evaluate(): number;
    numerator(): NerdamerResult;
    denominator(): NerdamerResult;
    simplify(): NerdamerResult;
    expand(): NerdamerResult;
    sub(variable: string, value: string | number): NerdamerResult;
    symbols(): string[];
    variables(): string[];
    equations(): any;
  }

  interface NerdamerStatic {
    (expression: string, subs?: any, option?: any): NerdamerResult;
    integrate(expression: string, variable?: string): NerdamerResult;
    diff(expression: string, variable?: string, times?: number): NerdamerResult;
    solve(expression: string, variable?: string): NerdamerResult;
    solveEquations(equations: string[]): any;
    setVar(name: string, value: any): void;
    getVar(name: string): any;
    convertToLaTeX(string: string): string;
    vector(components: any[]): NerdamerResult;
    matrix(matrix: any[][]): NerdamerResult;
    flush(): void;
  }

  const nerdamer: NerdamerStatic;
  export = nerdamer;
}

declare var nerdamer: any; 