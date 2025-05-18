import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ConvertedLogic {
  premises: string[];
  conclusion: string;
}

export interface NaturalLanguageRequest {
  premises: string[];
  conclusion: string;
  useLemmatization?: boolean;
}

export interface RelationExtractionResponse {
  method: string;
  relations: Array<{subject: string, relation: string, object: string}>;
  sentence: string;
}

@Injectable({
  providedIn: 'root'
})
export class Z3SolverService {
  private apiUrl = 'http://localhost:5000';

  constructor(private http: HttpClient) { }

  solveEquation(equation: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/solver`, { equation });
  }

  addConstraint(constraint: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/add_constraint`, { constraint });
  }

  checkSatisfiability(): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/check_satisfiability`, {});
  }

  proveTheorem(premises: string[], conclusion: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/prove_theorem`, { 
      premises, 
      conclusion 
    });
  }

  convertNaturalLanguage(premises: string[], conclusion: string, useLemmatization: boolean = true): Observable<ConvertedLogic> {
    const request: NaturalLanguageRequest = {
      premises,
      conclusion,
      useLemmatization
    };
    
    return this.http.post<ConvertedLogic>(`${this.apiUrl}/convert_natural_language`, request);
  }

  extractRelations(sentence: string): Observable<RelationExtractionResponse> {
    return this.http.post<RelationExtractionResponse>(`${this.apiUrl}/extract_relations`, { 
      sentence 
    });
  }
} 