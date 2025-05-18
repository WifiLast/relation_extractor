import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-z3-solver-new',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './z3-solver-new.component.html',
  styleUrls: ['./z3-solver.component.css']
})
export class Z3SolverNewComponent implements OnInit {
  // Basic component properties
  activeTab = 'solver';
  result = '';
  error = '';
  history: { type: string, input: string, output: string }[] = [];

  // Neo4j related variables
  neo4jSearchQuery = '';
  relatedRelations: Array<{subject: string, relation: string, object: string}> = [];
  extractedRelations: Array<{subject: string, relation: string, object: string, useAsPremise?: boolean}> = [];
  neo4jApiUrl = 'http://localhost:5000';
  mongodbApiUrl = 'http://localhost:5000'; // MongoDB API URL

  constructor(private http: HttpClient) {}

  ngOnInit() {
    // Initialize component
  }

  // Function to switch between tabs
  switchTab(tabName: string) {
    this.activeTab = tabName;
  }

  // Function to clear history
  clearHistory() {
    this.history = [];
  }

  // Track by function for ngFor
  trackByIndex(index: number): number {
    return index;
  }

  // Neo4j related functions
  // Function to use a found relation in the current relation list
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

  // Function to find related relations from Neo4j database
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
      },
      error: (error) => {
        this.error = `Error finding related relations: ${error.message || error}`;
        console.error('Neo4j search error:', error);
        this.relatedRelations = [];
      }
    });
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
      },
      error: (error) => {
        this.error = `Error saving relations: ${error.message || error}`;
        console.error('Neo4j save error:', error);
      }
    });
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
      },
      error: (error) => {
        this.error = `Error saving relations: ${error.message || error}`;
        console.error('MongoDB save error:', error);
      }
    });
  }

  // Function to find related relations from MongoDB database
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
      },
      error: (error) => {
        this.error = `Error finding related relations: ${error.message || error}`;
        console.error('MongoDB search error:', error);
        this.relatedRelations = [];
      }
    });
  }

  // Add other methods as needed for the component functionality
} 