#!/usr/bin/env python
# coding: utf-8

a, b = 0, 1
while a < 10:
    # print(a, end=',')
    a, b = b, a+b

point = (x, 1)
match point:
    case(0, 0):
        print("Origin")
    case(0, y):
        print(f"Y={y}")
    case(x, 0):
        print(f"X={x}")
    case(x, y):
        print(f"X={x}, Y={y}")
    case _:
        raise ValueError("Not a point")
