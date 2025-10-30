import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Z3SolverComponent } from './z3-solver/z3-solver.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, Z3SolverComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  title = 'Z3 Solver';
}
