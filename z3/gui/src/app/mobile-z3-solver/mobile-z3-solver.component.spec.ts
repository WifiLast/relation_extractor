import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MobileZ3SolverComponent } from './mobile-z3-solver.component';

describe('MobileZ3SolverComponent', () => {
  let component: MobileZ3SolverComponent;
  let fixture: ComponentFixture<MobileZ3SolverComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MobileZ3SolverComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(MobileZ3SolverComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
