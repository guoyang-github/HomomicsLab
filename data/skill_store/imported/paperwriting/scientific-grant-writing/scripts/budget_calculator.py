#!/usr/bin/env python3
"""
Budget Calculator for Grant Proposals
Calculate personnel costs, fringe benefits, indirect costs, and multi-year totals.
"""

import sys
import argparse
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class Personnel:
    name: str
    role: str
    base_salary: float
    effort_percent: float
    fringe_rate: float = 0.30
    annual_inflation: float = 0.03

    def annual_cost(self, year: int) -> float:
        """Calculate annual cost for a given year (0-indexed)."""
        inflated_salary = self.base_salary * ((1 + self.annual_inflation) ** year)
        salary_cost = inflated_salary * (self.effort_percent / 100)
        fringe = salary_cost * self.fringe_rate
        return salary_cost + fringe


@dataclass
class BudgetItem:
    category: str
    description: str
    year1: float
    year2: float = 0.0
    year3: float = 0.0
    year4: float = 0.0
    year5: float = 0.0

    def total(self) -> float:
        return self.year1 + self.year2 + self.year3 + self.year4 + self.year5

    def by_year(self) -> List[float]:
        return [self.year1, self.year2, self.year3, self.year4, self.year5]


class BudgetCalculator:
    """Calculate grant proposal budgets with inflation and fringe."""

    def __init__(
        self,
        indirect_rate: float = 0.55,
        indirect_base: str = "salary_plus_fringe",
    ):
        self.indirect_rate = indirect_rate
        self.indirect_base = indirect_base
        self.personnel: List[Personnel] = []
        self.other_items: List[BudgetItem] = []

    def add_personnel(
        self,
        name: str,
        role: str,
        base_salary: float,
        effort_percent: float,
        fringe_rate: float = 0.30,
    ) -> None:
        """Add a personnel line item."""
        self.personnel.append(
            Personnel(name, role, base_salary, effort_percent, fringe_rate)
        )

    def add_item(
        self,
        category: str,
        description: str,
        year1: float,
        year2: float = 0.0,
        year3: float = 0.0,
        year4: float = 0.0,
        year5: float = 0.0,
    ) -> None:
        """Add a non-personnel budget item."""
        self.other_items.append(
            BudgetItem(category, description, year1, year2, year3, year4, year5)
        )

    def calculate(self, years: int = 3) -> Dict:
        """Calculate full budget breakdown."""
        years = min(years, 5)

        # Personnel costs by year
        personnel_by_year = [0.0] * years
        for person in self.personnel:
            for y in range(years):
                personnel_by_year[y] += person.annual_cost(y)

        # Other costs by year
        other_by_year = [0.0] * years
        for item in self.other_items:
            for y in range(years):
                other_by_year[y] += item.by_year()[y]

        # Direct costs by year
        direct_by_year = [
            personnel_by_year[y] + other_by_year[y] for y in range(years)
        ]

        # Indirect costs
        if self.indirect_base == "salary_plus_fringe":
            indirect_by_year = [p * self.indirect_rate for p in personnel_by_year]
        else:
            indirect_by_year = [d * self.indirect_rate for d in direct_by_year]

        # Totals
        total_direct = sum(direct_by_year)
        total_indirect = sum(indirect_by_year)
        total_cost = total_direct + total_indirect

        return {
            "personnel": {
                "items": [asdict(p) for p in self.personnel],
                "by_year": personnel_by_year,
                "total": sum(personnel_by_year),
            },
            "other_direct": {
                "items": [asdict(i) for i in self.other_items],
                "by_year": other_by_year,
                "total": sum(other_by_year),
            },
            "direct_costs": {
                "by_year": direct_by_year,
                "total": total_direct,
            },
            "indirect_costs": {
                "by_year": indirect_by_year,
                "total": total_indirect,
                "rate": self.indirect_rate,
            },
            "total_cost": total_cost,
            "years": years,
        }

    def print_budget(self, years: int = 3) -> None:
        """Print formatted budget summary."""
        result = self.calculate(years)

        print("\n" + "=" * 70)
        print("GRANT BUDGET SUMMARY")
        print("=" * 70)

        # Personnel
        print("\nPERSONNEL:")
        print(f"{'Name':<20} {'Role':<20} {'Effort':<8} {'Y1':<12} {'Y2':<12} {'Y3':<12}")
        print("-" * 70)
        for p in self.personnel:
            costs = [p.annual_cost(y) for y in range(years)]
            cost_strs = [f"${c:,.0f}" for c in costs]
            print(f"{p.name:<20} {p.role:<20} {p.effort_percent:>5.0f}%  " + "  ".join(cost_strs))

        # Other items
        if self.other_items:
            print("\nOTHER DIRECT COSTS:")
            print(f"{'Category':<20} {'Description':<25} {'Y1':<12} {'Y2':<12} {'Y3':<12}")
            print("-" * 70)
            for item in self.other_items:
                costs = item.by_year()[:years]
                cost_strs = [f"${c:,.0f}" for c in costs]
                print(f"{item.category:<20} {item.description:<25} " + "  ".join(cost_strs))

        # Summary
        print("\n" + "-" * 70)
        print("BUDGET SUMMARY:")
        year_labels = [f"Year {i+1}" for i in range(years)]
        print(f"{'Category':<25} " + "  ".join(f"{yl:<12}" for yl in year_labels))
        print("-" * 70)

        personnel_years = result["personnel"]["by_year"]
        other_years = result["other_direct"]["by_year"]
        direct_years = result["direct_costs"]["by_year"]
        indirect_years = result["indirect_costs"]["by_year"]

        print("Personnel Costs        " + "  ".join(f"${c:>10,.0f}" for c in personnel_years))
        print("Other Direct Costs     " + "  ".join(f"${c:>10,.0f}" for c in other_years))
        print("Direct Costs Total     " + "  ".join(f"${c:>10,.0f}" for c in direct_years))
        print(f"Indirect Costs ({self.indirect_rate:.0%})   " + "  ".join(f"${c:>10,.0f}" for c in indirect_years))
        print("-" * 70)
        total_years = [direct_years[i] + indirect_years[i] for i in range(years)]
        print("TOTAL COSTS            " + "  ".join(f"${c:>10,.0f}" for c in total_years))
        print(f"\nGRAND TOTAL: ${result['total_cost']:,.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate grant proposal budgets"
    )
    parser.add_argument(
        "--indirect-rate",
        type=float,
        default=0.55,
        help="Indirect cost rate (e.g., 0.55 for 55%%)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        choices=[1, 2, 3, 4, 5],
        help="Number of years",
    )
    parser.add_argument(
        "--json",
        help="Output budget as JSON to file",
    )
    parser.add_argument(
        "--config",
        help="JSON config file with personnel and items",
    )
    args = parser.parse_args()

    calc = BudgetCalculator(indirect_rate=args.indirect_rate)

    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Error reading config file: {exc}", file=sys.stderr)
            sys.exit(1)
        for p in config.get("personnel", []):
            calc.add_personnel(
                p["name"],
                p["role"],
                p["base_salary"],
                p.get("effort_percent", 100),
                p.get("fringe_rate", 0.30),
            )
        for item in config.get("items", []):
            calc.add_item(
                item["category"],
                item["description"],
                item.get("year1", 0),
                item.get("year2", 0),
                item.get("year3", 0),
                item.get("year4", 0),
                item.get("year5", 0),
            )
    else:
        # Example budget
        calc.add_personnel("PI", "Principal Investigator", 150000, 10, 0.30)
        calc.add_personnel("Co-I", "Co-Investigator", 140000, 5, 0.30)
        calc.add_personnel("Postdoc", "Postdoctoral Researcher", 55000, 100, 0.30)
        calc.add_item("Travel", "Conferences", 3000, 3000, 3000)
        calc.add_item("Supplies", "Lab consumables", 5000, 5000, 5000)
        calc.add_item("Equipment", "Computer workstation", 2500, 0, 0)

    calc.print_budget(args.years)

    if args.json:
        result = calc.calculate(args.years)
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nBudget saved to {args.json}")


if __name__ == "__main__":
    main()
