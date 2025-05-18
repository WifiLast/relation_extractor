import { Routes } from '@angular/router';
import { Z3SolverComponent } from './z3-solver/z3-solver.component';
import { Z3SolverNewComponent } from './z3-solver/z3-solver-new.component';

export const routes: Routes = [
  { path: '', component: Z3SolverComponent },
  { path: 'new', component: Z3SolverNewComponent },
];
