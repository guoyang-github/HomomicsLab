#!/usr/bin/env python3
"""
Simple electrical circuit using Schemdraw.

Demonstrates: Standard circuit symbols, proper connection rendering,
and vector export.

Install: pip install schemdraw
Run: python schemdraw_circuit.py
Output: circuit.pdf
"""

import schemdraw
import schemdraw.elements as elm


def main():
    with schemdraw.Drawing() as d:
        d.config(unit=0.5)
        elm.SourceV().label('5V')
        elm.Resistor().right().label('1kΩ')
        elm.Capacitor().down().label('10µF')
        elm.Line().left()
        elm.Ground()

    d.save('circuit.pdf')
    print("Saved: circuit.pdf")


if __name__ == '__main__':
    main()
